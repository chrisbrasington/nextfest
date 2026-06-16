"""Look up a game's name and store URL from its appid.

Uses the public store appdetails endpoint (no API key). Stays usable offline:
on any failure it falls back to a bare appid-based store URL and an empty name
so the user can fill things in by hand.
"""
import re
from dataclasses import dataclass

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"


@dataclass
class AppInfo:
    appid: int
    name: str          # demo name with trailing " Demo" stripped
    raw_name: str      # exactly what Steam returned
    is_demo: bool
    store_appid: int   # base game's appid if this is a demo, else appid
    store_url: str


def _store_url(appid, name):
    """Build the canonical store URL form used in the markdown:
    https://store.steampowered.com/app/<appid>/<Name_With_Underscores>/
    """
    if name:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        return f"https://store.steampowered.com/app/{appid}/{slug}/"
    return f"https://store.steampowered.com/app/{appid}/"


def _strip_demo(name):
    return re.sub(r"\s*Demo\s*$", "", name).strip()


def appdetails(appid, timeout=8):
    """Best-effort lookup. Never raises; returns an AppInfo with fallbacks."""
    appid = int(appid)
    fallback = AppInfo(
        appid=appid, name="", raw_name="", is_demo=False,
        store_appid=appid, store_url=_store_url(appid, ""),
    )
    if requests is None:
        return fallback
    try:
        resp = requests.get(
            APPDETAILS_URL,
            params={"appids": appid, "l": "english"},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json().get(str(appid), {})
        if not payload.get("success"):
            return fallback
        data = payload["data"]
        raw_name = data.get("name", "") or ""
        is_demo = data.get("type") == "demo"
        full = data.get("fullgame") or {}
        store_appid = int(full.get("appid") or appid)
        name = _strip_demo(raw_name)
        return AppInfo(
            appid=appid,
            name=name,
            raw_name=raw_name,
            is_demo=is_demo,
            store_appid=store_appid,
            store_url=_store_url(store_appid, name),
        )
    except Exception:
        return fallback


if __name__ == "__main__":
    import sys
    info = appdetails(sys.argv[1] if len(sys.argv) > 1 else 1799840)
    print(info)
