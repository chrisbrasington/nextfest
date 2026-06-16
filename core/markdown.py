"""Render, parse, and upsert game entries in a month markdown file.

Reproduces the exact format of the existing files (e.g. 2025_Dec.md):

    | [Title](#anchor)            | 45 minutes | YES | tags |   <- summary table row
    ...
    # Title
    - **Steam Page**: [Title](url)
    - **Total Play Time**: 45 minutes
    - **Will Purchase**: YES
    - **Type**: tags
    > 🕹️ **Description**: ...
    >
    > 👍👎  **Feedback**: ...
    [![Thumbnail](img/thumbnails/F)](img/<slug>/<game>/F)   <- gallery

Upsert edits the text in place (replace the matching row + section, otherwise
insert) so diffs against hand-edited files stay small.
"""
import re

from . import config
from .models import GameEntry, DEFAULT_FEEDBACK_EMOJI

# --- time helpers (kept compatible with the old add.py) --------------------

def format_time_played(time_played):
    """'45' -> '45 minutes'; '1.5' -> '1.5 hours'; '2' with a dot stays hours."""
    time_played = str(time_played).strip()
    if "." in time_played:
        hours = float(time_played)
        return f"{hours:.1f} hours" if hours != int(hours) else f"{int(hours)} hours"
    return f"{int(time_played)} minutes"


def parse_time(time_str):
    """A '45 minutes' / '1.8 hours' string -> hours (float) for sorting."""
    time_str = (time_str or "").replace("+", "").strip()
    if "hours" in time_str:
        try:
            return float(time_str.replace(" hours", ""))
        except ValueError:
            return 0
    if "minutes" in time_str:
        try:
            return int(time_str.replace(" minutes", "")) / 60
        except ValueError:
            return 0
    return 0


# --- rendering -------------------------------------------------------------

def render_row(entry):
    """One summary-table row, padded to match the existing files."""
    link = f"| [{entry.title}](#{entry.anchor})".ljust(60)
    time = f"| {entry.playtime}".ljust(18)
    purchase = f"| {entry.will_purchase}".ljust(16)
    tags = f"| {entry.tags}".ljust(46)
    return f"{link}{time}{purchase}{tags}|"


def _render_feedback_body(feedback):
    """Feedback prose -> blockquote paragraphs separated by blank quote lines."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", feedback.strip()) if p.strip()]
    if not paras:
        return ""
    out = paras[0]
    for p in paras[1:]:
        out += f"\n> \n> {p}"
    return out


def render_gallery(entry, ctx):
    """Clickable-thumbnail markdown lines for the entry's screenshots."""
    lines = []
    for fn in entry.screenshots:
        thumb = f"img/thumbnails/{fn}"
        full = f"img/{ctx.img_slug}/{entry.slug}/{fn}"
        lines.append(f"[![Thumbnail]({thumb})]({full})")
    return "\n".join(lines)


def render_detail(entry, ctx):
    """A full game detail section (heading, metadata, blockquote, gallery)."""
    emoji = entry.feedback_emoji or DEFAULT_FEEDBACK_EMOJI
    desc = entry.description.strip()
    fb = _render_feedback_body(entry.feedback)
    section = (
        f"# {entry.title}\n\n"
        f"- **Steam Page**: [{entry.title}]({entry.store_url})\n"
        f"- **Total Play Time**: {entry.playtime}\n"
        f"- **Will Purchase**: {entry.will_purchase}\n"
        f"- **Type**: {entry.tags}\n\n"
        f"> 🕹️ **Description**: {desc}\n"
        f"> \n"
        f"> {emoji}  **Feedback**: {fb}\n"
    )
    gallery = render_gallery(entry, ctx)
    if gallery:
        section += "\n" + gallery + "\n"
    return section


# --- parsing ---------------------------------------------------------------

_SECTION_RE = re.compile(r"^# (.+)$", re.MULTILINE)


def _split_sections(content):
    """Yield (title, body_text, start, end) for every '# ' heading block.

    The first block is the page title + table; callers skip it.
    """
    matches = list(_SECTION_RE.finditer(content))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        yield m.group(1).strip(), content[start:end], start, end


def parse_entry(body, title):
    """Parse one detail-section body into a GameEntry."""
    entry = GameEntry(title=title)

    m = re.search(r"\*\*Steam Page\*\*: \[[^\]]*\]\(([^)]+)\)", body)
    if m:
        entry.store_url = m.group(1).strip()
        am = re.search(r"/app/(\d+)", entry.store_url)
        if am:
            entry.appid = int(am.group(1))

    m = re.search(r"\*\*Total Play Time\*\*:\s*(.+)", body)
    if m:
        entry.playtime = m.group(1).strip()
    m = re.search(r"\*\*Will Purchase\*\*:\s*(.*)", body)
    if m:
        entry.will_purchase = m.group(1).strip()
    m = re.search(r"\*\*Type\*\*:\s*(.*)", body)
    if m:
        entry.tags = m.group(1).strip()

    m = re.search(r"\*\*Description\*\*:\s*(.*)", body)
    if m:
        entry.description = m.group(1).strip()

    # Feedback: find the single line carrying the **Feedback**: marker, take the
    # emoji prefix from it, then collect the quoted body until the gallery/EOF.
    lines = body.split("\n")
    fb_idx = next((i for i, ln in enumerate(lines) if "**Feedback**:" in ln), None)
    if fb_idx is not None:
        head, _, rest = lines[fb_idx].partition("**Feedback**:")
        entry.feedback_emoji = re.sub(r"^>\s*", "", head).strip() or DEFAULT_FEEDBACK_EMOJI
        body_lines = [rest] + lines[fb_idx + 1:]
        paras, cur = [], []
        for line in body_lines:
            if line.lstrip().startswith("[![Thumbnail]"):
                break
            stripped = re.sub(r"^>\s?", "", line).rstrip()
            if stripped == "":
                if cur:
                    paras.append(" ".join(cur).strip())
                    cur = []
            else:
                cur.append(stripped)
        if cur:
            paras.append(" ".join(cur).strip())
        entry.feedback = "\n\n".join(p for p in paras if p)

    entry.screenshots = re.findall(r"\]\(img/[^)]+/([^/)]+)\)\s*$", body, re.MULTILINE)
    return entry


def parse_entries(content):
    """All game entries in a month file (the page-title block is skipped)."""
    entries = []
    for i, (title, body, _s, _e) in enumerate(_split_sections(content)):
        if i == 0:
            continue  # page title + table
        entries.append(parse_entry(body, title))
    return entries


# --- upsert ----------------------------------------------------------------

EMPTY_FILE_TEMPLATE = (
    "# {label}\n\n"
    "| Game Title                                                                          "
    "| Total Play Time | Will Purchase | Type                                        |\n"
    "|------------------------------------------------------------------------------------"
    "-|-----------------|---------------|---------------------------------------------|\n"
)


def _table_bounds(lines):
    """(first_row_index, end_index) for the summary table; rows live in [start, end)."""
    header = next((i for i, ln in enumerate(lines) if "| Game Title" in ln), None)
    if header is None:
        return None, None
    start = header + 2  # skip header + separator
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return start, end


def _upsert_row(lines, entry):
    start, end = _table_bounds(lines)
    if start is None:
        return lines
    anchor_tag = f"(#{entry.anchor})"
    # drop any existing row for this anchor
    lines = [ln for i, ln in enumerate(lines)
             if not (start <= i < end and anchor_tag in ln)]
    start, end = _table_bounds(lines)
    row = render_row(entry)
    new_hours = parse_time(entry.playtime)
    for i in range(start, end):
        cur = parse_time(lines[i].split("|")[2].strip())
        if new_hours > cur:
            lines.insert(i, row)
            return lines
    lines.insert(end, row)
    return lines


def upsert(content, entry, ctx):
    """Insert or update entry's row + detail section. Returns new content."""
    if "| Game Title" not in content:
        content = EMPTY_FILE_TEMPLATE.format(label=ctx.label)

    # Replace or append the detail section.
    detail = render_detail(entry, ctx)
    found = False
    for i, (title, _body, start, end) in enumerate(_split_sections(content)):
        if i == 0:
            continue
        if config.title_anchor(title) == entry.anchor:
            content = content[:start] + detail + "\n" + content[end:]
            found = True
            break
    if not found:
        content = content.rstrip() + "\n\n" + detail

    # Update the table row.
    lines = content.split("\n")
    lines = _upsert_row(lines, entry)
    return "\n".join(lines)
