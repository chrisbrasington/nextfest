# Next Fest Logger (GUI)

A small Tkinter app for logging the demos you play into the month's markdown file
and copying a ready-to-paste post for Discord.

## Run

```
pip install -r requirements.txt
python -m gui.app
```

Reads your Steam screenshots and recently-played list from the local Steam
install. Drag-drop of screenshots needs the optional `tkinterdnd2`; the
**Add screenshots** button works without it.

## Layout

- **Month** (top): pick the file you're logging into, or **New month…** to start one.
  New months get added to `README.md` automatically (on launch and on save).
- **Recently played (Steam)** (left): your last demos. Click one to load it.
- **In this month** (left): games already logged this month, newest at top. Click to edit.
- **Form** (center): title, Steam URL, playtime, tags, Will-get, verdict, description, feedback.
- **Screenshots** (center): tiles you can click to select. Header shows the count
  (`N found · M selected`). Hover a tile for a large preview.

## Logging a game

1. Click a game in **Recently played** (or an existing one under **In this month**).
2. Edit the fields. Playtime from Steam is cumulative — fix it to this session.
3. Pick screenshots: click Steam tiles to select, and/or **Add screenshots** to pull
   in your own image files. Already-saved repo shots show up preselected.
4. **💾 Save to markdown** (or **Ctrl+S**) — writes the entry and copies the chosen
   screenshots into `img/<month>/<slug>/`.
5. **📋 Copy for Discord** — puts a formatted post on your clipboard. Screenshots go
   in by hand; **📂 Open screenshot folder** opens the folder to drag them from.

## Notes

- Unsaved edits are guarded: the title bar shows `*  (unsaved)`, and closing the app
  or switching games prompts to Save / Discard / Cancel.
- Steam screenshots take priority in the grid, but anything already saved in the repo
  (even from an older month) still appears.
- **🆕 Clear form** resets to a blank entry.
