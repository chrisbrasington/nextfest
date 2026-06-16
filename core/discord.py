"""Render a Discord post (text only) and put it on the clipboard.

Discord can't use the repo's relative image paths or intra-doc anchors, so this
is deliberately separate from the GitHub markdown. Screenshots go in by hand
(use screenshots.open_folder and drag them into Discord).
"""
import shutil
import subprocess


def render(entry):
    """Plain text suitable for pasting into Discord."""
    lines = [f"# **{entry.title}**"]
    if entry.store_url:
        lines.append(entry.store_url)

    meta = []
    if entry.playtime:
        meta.append(f"⏱️ {entry.playtime}")
    if entry.will_purchase:
        meta.append(f"💰 Will purchase: {entry.will_purchase}")
    if entry.tags:
        meta.append(f"🏷️ {entry.tags}")
    if meta:
        lines.append("  ·  ".join(meta))

    if entry.description.strip():
        lines.append("")
        lines.append(f"🕹️ {entry.description.strip()}")
    if entry.feedback.strip():
        lines.append("")
        lines.append(f"{entry.feedback_emoji} {entry.feedback.strip()}")

    return "\n".join(lines)


def copy_to_clipboard(text):
    """Copy text to the Wayland clipboard via wl-copy. Returns True on success."""
    tool = shutil.which("wl-copy") or shutil.which("xclip")
    if not tool:
        return False
    try:
        if tool.endswith("xclip"):
            subprocess.run([tool, "-selection", "clipboard"],
                           input=text.encode(), check=True)
        else:
            subprocess.run([tool], input=text.encode(), check=True)
        return True
    except Exception:
        return False
