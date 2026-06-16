"""Read recently-played games from Steam's localconfig.vdf.

The apps block lives at UserLocalConfigStore > Software > Valve > Steam > apps,
mapping <appid> -> {LastPlayed: epoch, Playtime: cumulative_minutes, ...}.

NOTE: Playtime is the cumulative lifetime total, not the last session. Treat the
returned minutes as a suggestion only.
"""
from dataclasses import dataclass

from . import config

try:
    import vdf
except ImportError:  # pragma: no cover - dependency listed in requirements.txt
    vdf = None


@dataclass
class PlayedGame:
    appid: int
    last_played: int      # unix epoch seconds
    playtime_min: int     # cumulative minutes


def _get_ci(d, key):
    """Case-insensitive dict lookup (vdf preserves Steam's casing, which varies)."""
    if key in d:
        return d[key]
    low = key.lower()
    for k, v in d.items():
        if k.lower() == low:
            return v
    return None


def _apps_block(data):
    node = data
    for key in ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps"):
        if not isinstance(node, dict):
            return None
        node = _get_ci(node, key)
    return node if isinstance(node, dict) else None


def last_played(limit=15, path=None):
    """Return PlayedGame entries that have a LastPlayed, newest first."""
    if vdf is None:
        raise RuntimeError("The 'vdf' package is required: pip install vdf")
    path = path or config.localconfig_path()
    if not path:
        return []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        data = vdf.load(fh)
    apps = _apps_block(data)
    if not apps:
        return []

    games = []
    for appid, info in apps.items():
        if not isinstance(info, dict):
            continue
        lp = _get_ci(info, "LastPlayed")
        if not lp:
            continue
        try:
            appid_i = int(appid)
            lp_i = int(lp)
        except (TypeError, ValueError):
            continue
        pt = _get_ci(info, "Playtime") or 0
        try:
            pt_i = int(pt)
        except (TypeError, ValueError):
            pt_i = 0
        games.append(PlayedGame(appid=appid_i, last_played=lp_i, playtime_min=pt_i))

    games.sort(key=lambda g: g.last_played, reverse=True)
    return games[:limit] if limit else games


if __name__ == "__main__":  # quick manual check
    import datetime
    for g in last_played(10):
        when = datetime.datetime.fromtimestamp(g.last_played)
        print(f"{g.appid:>10}  {when:%Y-%m-%d %H:%M}  {g.playtime_min} min total")
