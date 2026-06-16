"""List Steam screenshots for a game and copy the chosen ones into the repo.

Copy is idempotent: existing full-size files and thumbnails are left alone.
"""
import os
import shutil

from PIL import Image

from . import config


def list_for_appid(appid):
    """Full-size screenshot paths for an appid, oldest first (matches filename order)."""
    d = config.screenshot_dir_for_appid(appid)
    if not d:
        return []
    files = [f for f in os.listdir(d)
             if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]
    return [os.path.join(d, f) for f in sorted(files)]


def steam_thumb_for(full_path):
    """Steam's own small thumbnail for a screenshot, if present (fast grid render)."""
    d = os.path.dirname(full_path)
    cand = os.path.join(d, "thumbnails", os.path.basename(full_path))
    return cand if os.path.isfile(cand) else None


def _make_thumb(src, dst):
    img = Image.open(src)
    thumb = img.copy()
    thumb.thumbnail(config.THUMB_SIZE)
    if thumb.mode in ("RGBA", "P"):
        thumb = thumb.convert("RGB")
    thumb.save(dst)


def copy_selected(entry, ctx, source_paths):
    """Copy chosen screenshots into img/<slug>/<game>/ + make 400x400 thumbs.

    Returns the list of basenames now associated with the entry (idempotent).
    Adds any new filenames to entry.screenshots without duplicating.
    """
    dest_dir = os.path.join(ctx.img_dir, entry.slug)
    os.makedirs(dest_dir, exist_ok=True)
    os.makedirs(config.THUMBS_DIR, exist_ok=True)

    for src in source_paths:
        fn = os.path.basename(src)
        dest = os.path.join(dest_dir, fn)
        if not os.path.exists(dest):
            shutil.copy2(src, dest)
        thumb = os.path.join(config.THUMBS_DIR, fn)
        if not os.path.exists(thumb):
            _make_thumb(dest, thumb)
        if fn not in entry.screenshots:
            entry.screenshots.append(fn)

    return entry.screenshots


def open_folder(entry, ctx):
    """Open the repo screenshot folder for this game (for manual Discord drag-in)."""
    import subprocess
    dest_dir = os.path.join(ctx.img_dir, entry.slug)
    if os.path.isdir(dest_dir):
        subprocess.Popen(["xdg-open", dest_dir])
        return dest_dir
    return None
