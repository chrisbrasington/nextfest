#!/usr/bin/env python
"""Next Fest logger GUI.

Pick your last-played Steam demo, click screenshots, type your impressions,
hit Save -> the month markdown is written and the Discord text is one click away.

Run from the repo root:  python -m gui.app   (or  python gui/app.py)
"""
import datetime
import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, simpledialog, ttk

from PIL import Image, ImageTk

# allow `python gui/app.py` as well as `python -m gui.app`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, markdown as md, screenshots, steam_api, steam_vdf, discord
from core.models import GameEntry

THUMB_DISPLAY = (200, 120)   # max tile image size; columns reflow to window width
TILE_PAD = 3

# modern dark palette
BG = "#1e1f2b"          # window background
SURFACE = "#282a3a"     # inputs / cards
SURFACE_HI = "#323548"  # hover / lighter surface
TEXT = "#e6e8f0"
MUTED = "#9aa0b5"
ACCENT = "#6c8cff"      # primary accent (indigo)
ACCENT_HI = "#8aa3ff"
BORDER = "#3a3d52"
SELECT = "#2d8cff"      # selected screenshot border

PURCHASE_OPTIONS = ["Yes", "No", "Maybe"]
VERDICT_OPTIONS = [("👍 Up", "👍"), ("🫱 Mid", "🫱"), ("👎 Down", "👎")]


def _purchase_from_text(text):
    """Map a stored 'Will Purchase' value onto the Yes/No/Maybe radios."""
    t = (text or "").strip().lower()
    if not t:
        return ""
    if any(k in t for k in ("yes", "yep", "yeah", "will", "likely", "lean", "buy")):
        return "Yes"
    if any(k in t for k in ("no", "nope", "pass", "skip", "won't", "wont")):
        return "No"
    return "Maybe"


def _verdict_from_emoji(emoji):
    """Map a stored feedback emoji prefix onto the up/mid/down radios."""
    e = emoji or ""
    up, down = "👍" in e, "👎" in e
    if up and not down:
        return "👍"
    if down and not up:
        return "👎"
    if any(h in e for h in ("🫱", "✋", "🤚", "🤙", "🫳")):
        return "🫱"
    return ""  # neutral/unrated -> no selection


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Next Fest Logger")
        self.geometry("1180x800")

        self.ctx = config.default_month_context()
        self.appid = None                 # currently loaded game's (demo) appid
        self.grid_sources = {}            # basename -> full-size source path
        self.thumb_refs = {}              # basename -> PhotoImage (keep alive!)
        self.selected = set()             # selected screenshot basenames
        self.tiles = {}                   # basename -> tile frame (for highlight)
        self.grid_order = []              # basenames in display order (for reflow)
        self.preview_win = None           # hover-preview Toplevel
        self.preview_cache = {}           # basename -> large PhotoImage
        self.purchase_var = tk.StringVar()
        self.verdict_var = tk.StringVar()
        self._dirty = False        # unsaved edits pending?
        self._loading = False      # suppress dirty-marking while populating the form

        self._apply_theme()
        self._build_ui()
        self._enable_dnd()
        self._wire_dirty_tracking()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-s>", lambda _e: (self.save(), "break")[1])
        config.reconcile_readme()      # pick up any month files missing from README
        self._reload_month()
        self.refresh_last_played()

    # ---- theme ------------------------------------------------------------
    def _apply_theme(self):
        self.configure(bg=BG)
        for name in ("TkDefaultFont", "TkTextFont"):
            try:
                f = tkfont.nametofont(name)
                f.configure(family="DejaVu Sans", size=10)
            except tk.TclError:
                pass
        self.header_font = tkfont.Font(family="DejaVu Sans", size=10, weight="bold")

        st = ttk.Style()
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE,
                     bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                     focuscolor=ACCENT)
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=TEXT)
        st.configure("Header.TLabel", background=BG, foreground=ACCENT_HI,
                     font=self.header_font)
        st.configure("Status.TLabel", background=BG, foreground=MUTED)

        st.configure("TButton", background=SURFACE_HI, foreground=TEXT,
                     borderwidth=0, focusthickness=0, padding=(10, 6))
        st.map("TButton", background=[("active", BORDER)])
        st.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                     borderwidth=0, padding=(12, 7))
        st.map("Accent.TButton", background=[("active", ACCENT_HI)])

        st.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                     insertcolor=TEXT, borderwidth=1, padding=4)
        st.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                     foreground=TEXT, arrowcolor=TEXT, borderwidth=1, padding=4)
        st.map("TCombobox", fieldbackground=[("readonly", SURFACE)],
               foreground=[("readonly", TEXT)])

        st.configure("TRadiobutton", background=BG, foreground=TEXT,
                     indicatorcolor=SURFACE, focuscolor=BG)
        st.map("TRadiobutton",
               background=[("active", BG)],
               indicatorcolor=[("selected", ACCENT)],
               foreground=[("active", ACCENT_HI)])

        st.configure("Vertical.TScrollbar", background=SURFACE, troughcolor=BG,
                     bordercolor=BG, arrowcolor=MUTED)

        self.option_add("*Listbox.background", SURFACE)
        self.option_add("*Listbox.foreground", TEXT)
        self.option_add("*Listbox.selectBackground", ACCENT)
        self.option_add("*Listbox.selectForeground", "#ffffff")
        self.option_add("*Listbox.borderWidth", 0)
        self.option_add("*Listbox.highlightThickness", 0)

    def _listbox(self, parent, **kw):
        return tk.Listbox(parent, bg=SURFACE, fg=TEXT, selectbackground=ACCENT,
                          selectforeground="#ffffff", borderwidth=0,
                          highlightthickness=0, activestyle="none", **kw)

    # ---- layout -----------------------------------------------------------
    def _build_ui(self):
        top = ttk.Frame(self, padding=6)
        top.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(top, text="Month:").pack(side=tk.LEFT)
        self.month_var = tk.StringVar()
        self.month_combo = ttk.Combobox(top, textvariable=self.month_var,
                                        width=22, state="readonly")
        self.month_combo.pack(side=tk.LEFT, padx=4)
        self.month_combo.bind("<<ComboboxSelected>>", self._on_month_change)
        ttk.Button(top, text="New month…", command=self._new_month).pack(side=tk.LEFT)
        ttk.Button(top, text="↻ Refresh Steam", command=self.refresh_last_played).pack(side=tk.LEFT, padx=12)
        self.status = ttk.Label(top, text="", style="Status.TLabel")
        self.status.pack(side=tk.LEFT, padx=8)

        body = ttk.Frame(self, padding=6)
        body.pack(fill=tk.BOTH, expand=True)

        # left: last-played + prior games
        left = ttk.Frame(body, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        ttk.Label(left, text="Recently played (Steam)", style="Header.TLabel").pack(anchor=tk.W)
        self.played_list = self._listbox(left, height=12, exportselection=False)
        self.played_list.pack(fill=tk.X, pady=(2, 0))
        self.played_list.bind("<<ListboxSelect>>", self._on_played_select)

        ttk.Label(left, text="In this month (click to edit)", style="Header.TLabel").pack(anchor=tk.W, pady=(12, 0))
        self.prior_list = self._listbox(left, height=12, exportselection=False)
        self.prior_list.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.prior_list.bind("<<ListboxSelect>>", self._on_prior_select)

        # center: form + screenshots
        center = ttk.Frame(body, padding=(10, 0))
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_form(center)
        self._build_grid(center)

        # bottom: actions + preview
        actions = ttk.Frame(self, padding=8)
        actions.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(actions, text="💾  Save to markdown", style="Accent.TButton", command=self.save).pack(side=tk.LEFT)
        ttk.Button(actions, text="📋  Copy for Discord", command=self.copy_discord).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="⬆️  Add screenshots", command=self.upload_screenshots).pack(side=tk.LEFT)
        ttk.Button(actions, text="📂  Open screenshot folder", command=self.open_folder).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="🆕  Clear form", command=self.clear_form).pack(side=tk.LEFT)

    def _build_form(self, parent):
        form = ttk.Frame(parent)
        form.pack(fill=tk.X)
        self.vars = {}

        def row(label, key, width=60):
            fr = ttk.Frame(form)
            fr.pack(fill=tk.X, pady=2)
            ttk.Label(fr, text=label, width=14).pack(side=tk.LEFT)
            var = tk.StringVar()
            ttk.Entry(fr, textvariable=var, width=width).pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.vars[key] = var

        row("Title", "title")
        row("Steam URL", "store_url")

        meta = ttk.Frame(form)
        meta.pack(fill=tk.X, pady=2)
        for lbl, key, w in (("Playtime", "playtime", 14), ("Type/tags", "tags", 22)):
            ttk.Label(meta, text=lbl).pack(side=tk.LEFT, padx=(0, 2))
            var = tk.StringVar()
            ttk.Entry(meta, textvariable=var, width=w).pack(side=tk.LEFT, padx=(0, 14))
            self.vars[key] = var

        radios = ttk.Frame(form)
        radios.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(radios, text="Will get").pack(side=tk.LEFT, padx=(0, 4))
        for opt in PURCHASE_OPTIONS:
            ttk.Radiobutton(radios, text=opt, value=opt,
                            variable=self.purchase_var).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(radios, text="     Verdict").pack(side=tk.LEFT, padx=(10, 4))
        for label, val in VERDICT_OPTIONS:
            ttk.Radiobutton(radios, text=label, value=val,
                            variable=self.verdict_var).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Label(form, text="Description (one line)", style="Header.TLabel").pack(anchor=tk.W, pady=(8, 0))
        self.desc_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.desc_var).pack(fill=tk.X)

        ttk.Label(form, text="Feedback — your impressions (blank line = new paragraph)",
                  style="Header.TLabel").pack(anchor=tk.W, pady=(8, 0))
        self.feedback_text = tk.Text(form, height=8, wrap=tk.WORD, bg=SURFACE, fg=TEXT,
                                     insertbackground=TEXT, borderwidth=0,
                                     highlightthickness=1, highlightbackground=BORDER,
                                     highlightcolor=ACCENT, padx=6, pady=6)
        self.feedback_text.pack(fill=tk.X, pady=(2, 0))

    def _build_grid(self, parent):
        self.grid_header = ttk.Label(parent, text="Screenshots", style="Header.TLabel")
        self.grid_header.pack(anchor=tk.W, pady=(10, 2))
        wrap = ttk.Frame(parent)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(wrap, highlightthickness=0, bg=BG)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.grid_frame = ttk.Frame(self.canvas)
        self.grid_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self._bind_wheel(self.canvas)
        self._bind_wheel(self.grid_frame)

    # ---- mouse-wheel scrolling -------------------------------------------
    _WHEEL_SEQS = ("<MouseWheel>", "<Button-4>", "<Button-5>")

    def _bind_wheel(self, widget):
        for seq in self._WHEEL_SEQS:
            widget.bind(seq, self._on_mousewheel)

    def _on_mousewheel(self, event):
        if event.num == 4:                       # X11 / XWayland wheel up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:                     # X11 / XWayland wheel down
            self.canvas.yview_scroll(1, "units")
        else:                                    # <MouseWheel> (delta-based)
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    # ---- month handling ---------------------------------------------------
    def _reload_month(self):
        files = config.discover_month_files()
        names = [os.path.basename(f) for f in files]
        cur = self.ctx.md_filename
        if cur not in names:
            names.insert(0, cur)
        self.month_combo["values"] = names
        self.month_var.set(cur)
        self._reload_prior()

    def _on_month_change(self, _evt):
        path = os.path.join(config.REPO_ROOT, self.month_var.get())
        self.ctx = config.month_context_for_file(path)
        self._reload_prior()

    def _new_month(self):
        suggested = config.current_month_filename()
        name = simpledialog.askstring("New month", "Filename:", initialvalue=suggested, parent=self)
        if not name:
            return
        if not name.endswith(".md"):
            name += ".md"
        self.ctx = config.month_context_for_file(os.path.join(config.REPO_ROOT, name))
        self._reload_month()

    def _reload_prior(self):
        self.prior_list.delete(0, tk.END)
        self._prior_entries = []
        if os.path.exists(self.ctx.md_path):
            with open(self.ctx.md_path, encoding="utf-8") as f:
                self._prior_entries = md.parse_entries(f.read())
            self._prior_entries.reverse()   # newest (last-appended) at top
        for e in self._prior_entries:
            self.prior_list.insert(tk.END, e.title)

    # ---- last-played ------------------------------------------------------
    def refresh_last_played(self):
        self.played_list.delete(0, tk.END)
        try:
            self._played = steam_vdf.last_played(15)
        except Exception as exc:
            self.status.config(text=f"Steam read failed: {exc}")
            self._played = []
            return
        for g in self._played:
            when = datetime.datetime.fromtimestamp(g.last_played).strftime("%b %d %H:%M")
            self.played_list.insert(tk.END, f"{g.appid} · {when} · {g.playtime_min}m")
        self.status.config(text=f"{len(self._played)} recent games. Resolving names…")
        threading.Thread(target=self._resolve_names, daemon=True).start()

    def _resolve_names(self):
        for idx, g in enumerate(list(self._played)):
            info = steam_api.appdetails(g.appid)
            name = info.name or info.raw_name
            if name:
                when = datetime.datetime.fromtimestamp(g.last_played).strftime("%b %d")
                label = f"{name} · {when} · {g.playtime_min}m"
                self.after(0, self._set_played_label, idx, label)
        self.after(0, lambda: self.status.config(text="Names resolved."))

    def _set_played_label(self, idx, label):
        if idx < self.played_list.size():
            self.played_list.delete(idx)
            self.played_list.insert(idx, label)

    def _on_played_select(self, _evt):
        sel = self.played_list.curselection()
        if not sel:
            return
        if not self._ok_to_leave():
            return
        g = self._played[sel[0]]
        self.status.config(text="Looking up game…")
        threading.Thread(target=self._load_played, args=(g,), daemon=True).start()

    def _load_played(self, g):
        info = steam_api.appdetails(g.appid)
        self.after(0, self._apply_played, g, info)

    def _apply_played(self, g, info):
        # If this game is already logged this month, load that entry for editing.
        title = info.name or info.raw_name
        existing = next((e for e in self._prior_entries
                         if title and e.anchor == config.title_anchor(title)), None)
        if existing:
            self._load_entry(existing, appid=g.appid)
            self.status.config(text=f"Editing existing entry: {title}")
            return
        self._begin_load()
        self.clear_form()
        self.appid = g.appid
        self.vars["title"].set(title)
        self.vars["store_url"].set(info.store_url)
        self.vars["playtime"].set(md.format_time_played(str(g.playtime_min)))
        self._grid_for_new(g.appid)
        self._end_load()
        self.status.config(text=f"Loaded {title or g.appid} (playtime is cumulative — edit it)")

    # ---- prior entry editing ---------------------------------------------
    def _on_prior_select(self, _evt):
        sel = self.prior_list.curselection()
        if not sel:
            return
        if not self._ok_to_leave():
            return
        entry = self._prior_entries[sel[0]]
        appid = entry.appid
        self._load_entry(entry, appid=appid)

    def _load_entry(self, entry, appid=None):
        self._begin_load()
        self.clear_form()
        self.appid = appid
        self.vars["title"].set(entry.title)
        self.vars["store_url"].set(entry.store_url)
        self.vars["playtime"].set(entry.playtime)
        self.vars["tags"].set(entry.tags)
        self.purchase_var.set(_purchase_from_text(entry.will_purchase))
        self.verdict_var.set(_verdict_from_emoji(entry.feedback_emoji))
        self.desc_var.set(entry.description)
        self.feedback_text.delete("1.0", tk.END)
        self.feedback_text.insert("1.0", entry.feedback)
        self._grid_for_entry(entry, appid)
        self._end_load()
        self.status.config(text=f"Editing: {entry.title}")

    # ---- screenshot grid --------------------------------------------------
    def _clear_grid(self):
        self._hide_preview()
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.thumb_refs.clear()
        self.grid_sources.clear()
        self.tiles.clear()
        self.grid_order = []
        self.preview_cache.clear()
        self.selected = set()
        if hasattr(self, "grid_header"):
            self._update_grid_header()

    def _grid_for_new(self, appid):
        """Fresh game just picked from Steam: Steam shots first (priority), then
        any shots already saved in the repo for this title (old games whose
        Steam screenshots are gone still show their saved ones)."""
        paths = screenshots.list_for_appid(appid)
        title = self.vars["title"].get().strip()
        if title:
            paths = paths + screenshots.list_in_repo_any(config.game_slug(title))
        self._render_grid(paths, preselect=[])

    def _grid_for_entry(self, entry, appid):
        """Existing entry: Steam shots for the appid take priority, then the
        already-saved repo shots (across any month) — preselected. The store
        appid often has no Steam shots; the saved ones still appear."""
        paths = []
        if appid:
            paths += screenshots.list_for_appid(appid)
        paths += screenshots.list_from_entry_paths(entry)   # exact gallery paths
        paths += screenshots.list_in_repo_any(entry.slug)   # slug-derived fallback
        self._render_grid(paths, preselect=list(entry.screenshots))

    def _render_grid(self, source_paths, preselect):
        self._clear_grid()
        self.canvas.yview_moveto(0)        # new game -> back to top
        self.selected = set(preselect)
        for path in source_paths:
            fn = os.path.basename(path)
            if fn in self.grid_sources:        # dedup (repo + steam overlap)
                continue
            self.grid_sources[fn] = path
            try:
                src = screenshots.steam_thumb_for(path) or path
                img = Image.open(src)
                img.thumbnail(THUMB_DISPLAY)
                photo = ImageTk.PhotoImage(img)
            except Exception:
                continue
            self.thumb_refs[fn] = photo
            tile = tk.Frame(self.grid_frame, bd=0, relief=tk.FLAT, bg=BORDER,
                            highlightthickness=3, highlightbackground=BORDER)
            lbl = tk.Label(tile, image=photo, bg=SURFACE, bd=0)
            lbl.pack(padx=2, pady=2)
            self.tiles[fn] = tile
            self.grid_order.append(fn)
            lbl.bind("<Button-1>", lambda e, b=fn: self._toggle(b))
            lbl.bind("<Enter>", lambda e, b=fn: self._show_preview(e, b))
            lbl.bind("<Motion>", lambda e, b=fn: self._move_preview(e))
            lbl.bind("<Leave>", lambda e: self._hide_preview())
            self._bind_wheel(tile)
            self._bind_wheel(lbl)
            self._paint_tile(fn)
        if not self.grid_sources:
            ttk.Label(self.grid_frame,
                      text="(no screenshots found — any already saved are still kept)").grid(row=0, column=0)
        self._update_grid_header()
        self._reflow()

    # ---- responsive layout ------------------------------------------------
    def _current_cols(self, width=None):
        if width is None:
            width = self.canvas.winfo_width()
        if width <= 1:
            width = 900
        tile_w = THUMB_DISPLAY[0] + 2 * TILE_PAD + 10
        return max(1, width // tile_w)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfigure(self.grid_window, width=event.width)
        self._reflow(event.width)

    def _reflow(self, width=None):
        if not self.grid_order:
            return
        cols = self._current_cols(width)
        for i, fn in enumerate(self.grid_order):
            tile = self.tiles.get(fn)
            if tile:
                tile.grid_configure(row=i // cols, column=i % cols,
                                    padx=TILE_PAD, pady=TILE_PAD, sticky="nw")
        total = self.grid_frame.grid_size()[0]
        for c in range(total):
            self.grid_frame.columnconfigure(c, weight=0)

    # ---- hover preview ----------------------------------------------------
    def _show_preview(self, event, basename):
        path = self.grid_sources.get(basename)
        if not path:
            return
        photo = self.preview_cache.get(basename)
        if photo is None:
            try:
                img = Image.open(path)
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                img.thumbnail((min(900, sw - 80), min(620, sh - 120)))
                photo = ImageTk.PhotoImage(img)
            except Exception:
                return
            self.preview_cache[basename] = photo
        if self.preview_win is None or not tk.Toplevel.winfo_exists(self.preview_win):
            self.preview_win = tk.Toplevel(self)
            self.preview_win.overrideredirect(True)
            self.preview_win.configure(bg=ACCENT)
            self._preview_label = tk.Label(self.preview_win, bd=0, bg=BG)
            self._preview_label.pack(padx=2, pady=2)
        self._preview_label.configure(image=photo)
        self._preview_label.image = photo
        self.preview_win.deiconify()
        self._move_preview(event)

    def _move_preview(self, event):
        win = self.preview_win
        if win is None or not tk.Toplevel.winfo_exists(win):
            return
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = event.x_root + 24
        y = event.y_root + 24
        if x + w > sw:
            x = event.x_root - w - 24
        if y + h > sh:
            y = sh - h - 20
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _hide_preview(self):
        if self.preview_win is not None and tk.Toplevel.winfo_exists(self.preview_win):
            self.preview_win.withdraw()

    # ---- adding screenshots (upload button + drag-drop) -------------------
    IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif")

    def upload_screenshots(self):
        self._add_uploads(self._pick_files())

    def _pick_files(self):
        """Native multi-select file picker. KDE's kdialog first (matches your
        Plasma theme, lets you type a path), then zenity, then Tk's dialog as a
        last resort. Returns a list of absolute paths ([] if cancelled)."""
        import shutil
        import subprocess

        home = os.path.expanduser("~")
        if shutil.which("kdialog"):
            r = subprocess.run(
                ["kdialog", "--getopenfilename", home,
                 "*.png *.jpg *.jpeg *.gif|Images", "--multiple", "--separate-output"],
                capture_output=True, text=True)
            return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []
        if shutil.which("zenity"):
            r = subprocess.run(
                ["zenity", "--file-selection", "--multiple", "--separator=\n",
                 "--title=Add screenshots",
                 "--file-filter=Images | *.png *.jpg *.jpeg *.gif"],
                capture_output=True, text=True)
            return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []
        from tkinter import filedialog
        return list(filedialog.askopenfilenames(
            title="Add screenshots",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif"), ("All files", "*.*")]))

    def _add_uploads(self, paths):
        """Fold external image files into the grid: appended, selected, ready to
        save. copy_selected() copies them into the repo on Save."""
        imgs = [p for p in paths
                if os.path.isfile(p) and p.lower().endswith(self.IMG_EXTS)]
        if not imgs:
            return
        current = list(self.grid_sources.values())   # preserve display order
        new = [p for p in imgs if os.path.basename(p) not in self.grid_sources]
        self.selected |= {os.path.basename(p) for p in new}
        self._render_grid(current + new, preselect=list(self.selected))
        self._mark_dirty()
        self.status.config(text=f"Added {len(new)} screenshot(s) — Save to keep them")

    def _enable_dnd(self):
        """Best-effort OS file drag-drop onto the grid (needs tkinterdnd2)."""
        self._dnd_on = False
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            TkinterDnD._require(self)
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind("<<Drop>>", self._on_drop)
            self._dnd_on = True
        except Exception:
            pass  # button-based upload still works

    def _on_drop(self, event):
        try:
            paths = list(self.tk.splitlist(event.data))   # handles {braced paths}
        except Exception:
            paths = event.data.split()
        self._add_uploads(paths)

    def _toggle(self, basename):
        if basename in self.selected:
            self.selected.discard(basename)
        else:
            self.selected.add(basename)
        self._paint_tile(basename)
        self._update_grid_header()
        self._mark_dirty()

    def _update_grid_header(self):
        total = len(self.grid_sources) + len([b for b in self.selected
                                              if b not in self.grid_sources])
        sel = len(self.selected)
        hint = "drag images here or use Add screenshots" if getattr(self, "_dnd_on", False) \
            else "use Add screenshots ⬆️"
        self.grid_header.config(text=f"Screenshots — {total} found · {sel} selected  ({hint})")

    def _paint_tile(self, basename):
        tile = self.tiles.get(basename)
        if tile:
            on = basename in self.selected
            tile.configure(highlightbackground=SELECT if on else BORDER,
                           bg=SELECT if on else BORDER)

    # ---- unsaved-changes tracking ----------------------------------------
    def _wire_dirty_tracking(self):
        for var in list(self.vars.values()) + [self.desc_var, self.purchase_var,
                                               self.verdict_var]:
            var.trace_add("write", self._mark_dirty)
        self.feedback_text.bind("<<Modified>>", self._on_text_modified)

    def _on_text_modified(self, _evt):
        if not self.feedback_text.edit_modified():
            return
        self.feedback_text.edit_modified(False)   # reset so the next edit fires
        self._mark_dirty()

    def _mark_dirty(self, *_):
        if self._loading or self._dirty:
            return
        self._set_dirty(True)

    def _begin_load(self):
        self._loading = True

    def _end_load(self):
        # Populating fires var traces and a queued Text <<Modified>> event. Stay
        # in loading mode until the event queue drains, THEN clear dirty — else
        # the late <<Modified>> marks an untouched game as edited.
        def done():
            self._loading = False
            self._set_dirty(False)
        self.after_idle(done)

    def _set_dirty(self, val):
        self._dirty = val
        self.title("Next Fest Logger" + ("  *  (unsaved)" if val else ""))

    def _ok_to_leave(self):
        """Gate any action that abandons the current form (close, switch games).
        Returns True if it's safe to proceed, False to abort."""
        if not self._dirty:
            return True
        ans = messagebox.askyesnocancel(
            "Unsaved changes", "Save your changes first?")
        if ans is None:            # Cancel -> abort
            return False
        if ans:                    # Yes -> save; block if it didn't take
            self.save()
            return not self._dirty  # save bailed (e.g. missing title)
        return True                # No -> discard

    def _on_close(self):
        if self._ok_to_leave():
            self.destroy()

    # ---- build entry from form -------------------------------------------
    def _form_entry(self):
        entry = GameEntry(
            title=self.vars["title"].get().strip(),
            store_url=self.vars["store_url"].get().strip(),
            playtime=self.vars["playtime"].get().strip(),
            will_purchase=self.purchase_var.get().strip(),
            tags=self.vars["tags"].get().strip(),
            feedback_emoji=self.verdict_var.get().strip() or "👍👎",
            description=self.desc_var.get().strip(),
            feedback=self.feedback_text.get("1.0", tk.END).strip(),
            appid=self.appid,
        )
        # screenshots in the grid's display order, selected only
        ordered = [fn for fn in self.grid_sources if fn in self.selected]
        # plus any selected that aren't in the current grid (already in repo)
        ordered += [fn for fn in self.selected if fn not in self.grid_sources]
        entry.screenshots = ordered
        return entry

    # ---- actions ----------------------------------------------------------
    def save(self):
        entry = self._form_entry()
        if not entry.title:
            messagebox.showwarning("Missing title", "A title is required.")
            return
        sources = [self.grid_sources[b] for b in entry.screenshots if b in self.grid_sources]
        try:
            screenshots.copy_selected(entry, self.ctx, sources)
        except Exception as exc:
            messagebox.showerror("Screenshot copy failed", str(exc))
            return
        content = ""
        if os.path.exists(self.ctx.md_path):
            with open(self.ctx.md_path, encoding="utf-8") as f:
                content = f.read()
        content = md.upsert(content, entry, self.ctx)
        with open(self.ctx.md_path, "w", encoding="utf-8") as f:
            f.write(content)
        config.reconcile_readme()      # a brand-new month file now exists -> index it
        self._reload_month()
        self.month_var.set(self.ctx.md_filename)
        self._set_dirty(False)
        self.status.config(text=f"Saved {entry.title} -> {self.ctx.md_filename}")

    def copy_discord(self):
        text = discord.render(self._form_entry())
        ok = discord.copy_to_clipboard(text)
        self.status.config(text="Copied Discord text" if ok else "Clipboard tool not found")
        if not ok:
            messagebox.showinfo("Discord text", text)

    def open_folder(self):
        path = screenshots.open_folder(self._form_entry(), self.ctx)
        self.status.config(text=f"Opened {path}" if path else "No folder yet (save first)")

    def clear_form(self):
        for var in self.vars.values():
            var.set("")
        self.purchase_var.set("")
        self.verdict_var.set("")
        self.desc_var.set("")
        self.feedback_text.delete("1.0", tk.END)
        self._clear_grid()
        self.appid = None
        if not self._loading:   # standalone "Clear form" -> clean slate, not dirty
            self._set_dirty(False)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
