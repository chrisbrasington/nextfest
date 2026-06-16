#!/usr/bin/env python
"""CLI to add/update a game in the current month's markdown file.

    python add.py <steam_url> <time_played> [tags] [--file 2026_June.md]

Now backed by the shared `core` package: de-hardcoded month, and it UPDATES an
existing entry instead of blindly appending a duplicate. Screenshots are handled
by the GUI (gui/app.py); this just writes the text entry.
"""
import os
import re
import sys

from core import config, markdown as md
from core.models import GameEntry


def extract_game_title(url):
    match = re.search(r"/app/\d+/(.*?)/", url)
    return match.group(1).replace("_", " ") if match else "Unknown Game"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    md_path = None
    if "--file" in argv:
        i = argv.index("--file")
        md_path = os.path.join(config.REPO_ROOT, argv[i + 1])
        del argv[i:i + 2]

    if not (2 <= len(argv) <= 3):
        print("Usage: python add.py <steam_url> <time_played> [tags] [--file NAME.md]")
        return 1

    steam_url, time_played = argv[0], argv[1]
    tags = argv[2] if len(argv) == 3 else ""

    ctx = config.month_context_for_file(md_path) if md_path else config.default_month_context()

    entry = GameEntry(
        title=extract_game_title(steam_url),
        store_url=steam_url,
        playtime=md.format_time_played(time_played),
        tags=tags,
    )

    content = ""
    if os.path.exists(ctx.md_path):
        with open(ctx.md_path, encoding="utf-8") as f:
            content = f.read()

    # If the game is already logged, keep its prose + screenshots; only refresh
    # the fields this CLI actually sets (url, playtime, tags).
    existing = next((e for e in md.parse_entries(content) if e.anchor == entry.anchor), None)
    if existing:
        entry.description = existing.description
        entry.feedback = existing.feedback
        entry.feedback_emoji = existing.feedback_emoji
        entry.screenshots = existing.screenshots
        if not tags:
            entry.tags = existing.tags

    content = md.upsert(content, entry, ctx)
    with open(ctx.md_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {entry.title} -> {ctx.md_filename}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
