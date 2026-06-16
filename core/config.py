"""Paths, month context, and slug helpers.

Single source of truth for where things live. Nothing else should hardcode a
month, a Steam path, or a slug rule.
"""
import glob
import os
import re
from dataclasses import dataclass
from datetime import datetime

# --- repo layout -----------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_ROOT = os.path.join(REPO_ROOT, "img")
THUMBS_DIR = os.path.join(IMG_ROOT, "thumbnails")
THUMB_SIZE = (400, 400)

# --- steam layout ----------------------------------------------------------

STEAM_USERDATA = os.path.expanduser("~/.local/share/Steam/userdata")
# Steam stores screenshots under <userdata>/<steamid>/760/remote/<appid>/screenshots
SCREENSHOT_SUBPATH = os.path.join("760", "remote")
LOCALCONFIG_SUBPATH = os.path.join("config", "localconfig.vdf")

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def steam_user_dirs():
    """Userdata account dirs that actually hold data (skip the '0' placeholder)."""
    if not os.path.isdir(STEAM_USERDATA):
        return []
    out = []
    for name in os.listdir(STEAM_USERDATA):
        if name == "0":
            continue
        d = os.path.join(STEAM_USERDATA, name)
        if os.path.isdir(d):
            out.append(d)
    return out


def localconfig_path():
    """Path to the localconfig.vdf for the first real Steam account, or None."""
    for d in steam_user_dirs():
        p = os.path.join(d, LOCALCONFIG_SUBPATH)
        if os.path.isfile(p):
            return p
    return None


def screenshot_dir_for_appid(appid):
    """Steam screenshot folder for an appid, or None if it has no screenshots."""
    for d in steam_user_dirs():
        p = os.path.join(d, SCREENSHOT_SUBPATH, str(appid), "screenshots")
        if os.path.isdir(p):
            return p
    return None


# --- slugs -----------------------------------------------------------------

def game_slug(title):
    """Folder-safe game slug: lowercase, spaces -> _, drop punctuation.

    Matches existing repo dirs like ``queens_domain`` and ``ardenfall``.
    """
    s = title.strip().lower()
    s = s.replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def title_anchor(title):
    """GitHub-style intra-doc anchor (matches add.py's old convert_title_to_anchor)."""
    return title.lower().replace(" ", "-").replace("'", "")


# --- month context ---------------------------------------------------------

@dataclass
class MonthContext:
    """One logging session/month: its markdown file + image folder."""
    md_path: str          # absolute path to YYYY_Mon.md
    img_slug: str         # e.g. "2026_june" -> img/2026_june/

    @property
    def md_filename(self):
        return os.path.basename(self.md_path)

    @property
    def img_dir(self):
        return os.path.join(IMG_ROOT, self.img_slug)

    @property
    def label(self):
        return self.md_filename.replace(".md", "").replace("_", " ")


def discover_month_files():
    """All YYYY_*.md session files in the repo, newest filename first.

    Excludes generated/aux files (all_games.md, *_awards.md).
    """
    files = sorted(glob.glob(os.path.join(REPO_ROOT, "20*.md")), reverse=True)
    out = []
    for f in files:
        name = os.path.basename(f)
        if name == "all_games.md" or "_awards" in name:
            continue
        out.append(f)
    return out


def img_slug_for_filename(md_filename):
    """img slug from a month filename: '2026_June.md' -> '2026_june'."""
    return md_filename.replace(".md", "").lower()


def month_context_for_file(md_path):
    name = os.path.basename(md_path)
    return MonthContext(md_path=os.path.abspath(md_path), img_slug=img_slug_for_filename(name))


def current_month_filename(now=None):
    """Suggested filename for the current month, e.g. '2026_June.md'."""
    now = now or datetime.now()
    return f"{now.year}_{_MONTHS[now.month - 1]}.md"


def default_month_context(now=None):
    """MonthContext for the current month, ready to log into even if the file
    doesn't exist yet (it's created on first save)."""
    target = os.path.join(REPO_ROOT, current_month_filename(now))
    return month_context_for_file(target)
