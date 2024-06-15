# Game Tracker Add Program (add.py)

## Overview
This Python script `add.py` is designed to update a Markdown file (`{markdown_filename}`) with new game entries. It extracts game details from a Steam URL, formats playtime, and optionally includes tags for categorization. The script ensures entries are sorted by playtime and updates both a table and a detailed section for each added game.

## Usage
To use the script, run it from the command line with the following arguments:
```
python add.py <steam_url> <time_played> [tags]
```

- `<steam_url>`: The URL of the game's Steam page.
- `<time_played>`: Total time played, specified in hours or minutes (e.g., "45", "1.5").
- `[tags]` (optional): Tags to categorize the game (e.g., "#action #tactics").

## Example
```
python add.py https://store.steampowered.com/app/1590760/Metal_Slug_Tactics/ 45 "#action #tactics"
```

## Output
After running the script with the above example, the Markdown file (`{markdown_filename}`) will be updated as follows:

### Table Entry
```
| [Metal Slug Tactics](#metal-slug-tactics)                 | 45 minutes      |               | #action #tactics                           |
```

### Detailed Section
```
# Metal Slug Tactics

- **Steam Page**: [Metal Slug Tactics](https://store.steampowered.com/app/1590760/Metal_Slug_Tactics/)
- **Total Play Time**: 45 minutes
- **Will Purchase**: 
- **Type**: #action #tactics

> 🕹️ **Description**: 
>
> 👍👎  **Feedback**: 
```