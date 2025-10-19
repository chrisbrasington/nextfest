import glob
import re
from pathlib import Path

MD_DIR = "."  # folder with markdown files
FILES = glob.glob(f"{MD_DIR}/202*.md")

games = []

def clean_title(title):
    """Remove thumbs up/down and extra whitespace"""
    return re.sub(r'[👍👎]', '', title).strip()

def extract_steam_link_after(text, start_pos):
    """Find first Steam URL after start_pos ignoring images and blockquotes"""
    lines = text[start_pos:].splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith('![') or line.startswith('>'):
            continue
        match = re.search(r'https://store\.steampowered\.com/app/\d+/.+?/', line)
        if match:
            return match.group(0)
    return ""

for file_path in FILES:
    file_name = Path(file_path).name
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    when_played = file_name.replace(".md", "").replace("_", " ")

    # Find all game headers
    headers = re.findall(r'^# (.+)$', content, re.MULTILINE)
    for game_name in headers:
        game_name_clean = clean_title(game_name)
        start_pos = content.find(f"# {game_name}")
        steam_link = extract_steam_link_after(content, start_pos)
        games.append((game_name_clean, when_played, steam_link))

# Remove duplicates (same name and URL)
seen = set()
unique_games = []
for g in games:
    key = (g[0].lower(), g[2])
    if key not in seen:
        seen.add(key)
        unique_games.append(g)

# Sort alphabetically
unique_games.sort(key=lambda x: x[0].lower())

# Write markdown table
output = ["| Game Name | When Played | Steam Link |",
          "|-----------|------------|------------|"]
for name, when, link in unique_games:
    output.append(f"| [{name}]({link}) | {when} | {link} |")

with open("all_games.md", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print(f"Processed {len(unique_games)} games into all_games.md")
