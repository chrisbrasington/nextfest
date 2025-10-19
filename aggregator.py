import glob
import re
from pathlib import Path

MD_DIR = "."  # folder with markdown files
FILES = glob.glob(f"{MD_DIR}/20*.md")  # all 20xx files

games = []

def clean_title(title):
    """Remove thumbs up/down and extra whitespace"""
    return re.sub(r'[👍👎]', '', title).strip()

def get_steam_header_image(steam_link):
    """Return the Steam header image URL from Steam link"""
    if not steam_link:
        return ""
    match = re.search(r'/app/(\d+)', steam_link)
    if match:
        app_id = match.group(1)
        return f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg"
    return ""

def extract_playtime_after(text, start_pos):
    """Find approximate playtime after start_pos"""
    lines = text[start_pos:].splitlines()
    for line in lines:
        line = line.strip()
        # ~XX minutes
        match = re.search(r'~\s*(\d+(\.\d+)?)\s*minutes', line, re.IGNORECASE)
        if match:
            return f"{match.group(1)} minutes"
        # ~X.Y hours
        match = re.search(r'~\s*(\d+(\.\d+)?)\s*hour', line, re.IGNORECASE)
        if match:
            hours = float(match.group(1))
            minutes = int(round(hours * 60))
            return f"{minutes} minutes"
    return ""

def extract_liked(text, start_pos):
    """Detect if user liked the game"""
    snippet = text[start_pos:start_pos+300].lower()
    if '👍' in snippet or 'like' in snippet or 'recommended' in snippet:
        return 'YES'
    return ''

def playtime_to_minutes(playtime_str):
    """Convert playtime string to minutes as integer"""
    if not playtime_str:
        return 0
    s = playtime_str.replace("~", "").strip().lower()
    if "minute" in s:
        try:
            return int(float(s.split()[0]))
        except ValueError:
            return 0
    if "hour" in s:
        try:
            return int(float(s.split()[0]) * 60)
        except ValueError:
            return 0
    return 0

def extract_steam_link_for_header(text, start_pos):
    """
    Extract the Steam link for a header+free-text game.
    Stops at the next header.
    Accepts links with or without trailing slash or name.
    """
    end_pos = text.find("\n# ", start_pos + 1)
    snippet = text[start_pos:end_pos] if end_pos != -1 else text[start_pos:]
    match = re.search(r'https://store\.steampowered\.com/app/(\d+)(?:/[^ \n]*)?/?', snippet)
    return match.group(0) if match else ""

for file_path in FILES:
    file_name = Path(file_path).name
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    when_played = file_name.replace(".md", "").replace("_", " ")

    # Detect table (2024+)
    table_rows = re.findall(r'\| \[([^\]]+)\]\(([^)]+)\)\s*\| ([^\|]*) \|', content)
    if table_rows:
        # Table format: use link from table itself
        for game_name, link, playtime in table_rows:
            game_name_clean = clean_title(game_name)
            liked = extract_liked(content, content.find(f"[{game_name}]({link})"))
            header_image = get_steam_header_image(link)
            games.append((game_name_clean, when_played, playtime.strip(), liked, link, header_image))
    else:
        # Header + free text format
        headers = re.findall(r'^# (.+)$', content, re.MULTILINE)
        for game_name in headers:
            game_name_clean = clean_title(game_name)
            start_pos = content.find(f"# {game_name}")
            steam_link = extract_steam_link_for_header(content, start_pos)
            header_image = get_steam_header_image(steam_link)
            playtime = extract_playtime_after(content, start_pos)
            liked = extract_liked(content, start_pos)
            games.append((game_name_clean, when_played, playtime, liked, steam_link, header_image))

# Remove duplicates (same name + Steam link)
seen = set()
unique_games = []
for g in games:
    key = (g[0].lower(), g[4])
    if key not in seen:
        seen.add(key)
        unique_games.append(g)

# Sort alphabetically
unique_games.sort(key=lambda x: x[0].lower())

# Summary
total_games = len(unique_games)
total_minutes = sum(playtime_to_minutes(g[2]) for g in unique_games)
total_hours = round(total_minutes / 60, 1)
total_liked = sum(1 for g in unique_games if g[3] == 'YES')

# Web-style summary
summary = (
    f"## 🎮 Game Collection Summary\n\n"
    f"**🕹️ Total Games:** {total_games}  |  "
    f"⏱️ Total Hours Played: {total_hours} hrs  |  "
    f"👍 Liked Games: {total_liked}\n\n"
    f"---\n"
)

# Markdown table with cover column
output = [summary,
          "| Cover | Game Name | When Played | Total Play Time | Liked | Steam Link |",
          "|-------|-----------|------------|----------------|-------|------------|"]

for name, when, playtime, liked, link, header_img in unique_games:
    cover_md = f"![{name}]({header_img})" if header_img else ""
    output.append(f"| {cover_md} | [{name}]({link}) | {when} | {playtime} | {liked} | {link} |")

with open("all_games.md", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print(f"Processed {len(unique_games)} games into all_games.md")
