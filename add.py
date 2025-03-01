import sys
import re
import os
import subprocess

def format_time_played(time_played):
    if '.' in time_played:
        hours = float(time_played)
        return f"{hours:.1f} hours" if hours != int(hours) else f"{int(hours)} hours"
    else:
        minutes = int(time_played)
        return f"{minutes} minutes"

def extract_game_title(url):
    match = re.search(r'/app/\d+/(.*)/', url)
    return match.group(1).replace('_', ' ') if match else "Unknown Game"

def convert_title_to_anchor(title):
    return title.lower().replace(' ', '-').replace('\'', '')

def parse_time(time_str):
    time_str = time_str.replace('+', '')
    if 'hours' in time_str:
        return float(time_str.replace(' hours', ''))
    elif 'minutes' in time_str:
        return int(time_str.replace(' minutes', '')) / 60
    return 0

def compare_times(new_time_str, current_time):
    new_time = parse_time(new_time_str)
    return new_time > current_time

def insert_game_into_table(content, title, formatted_time, steam_url, tags):
    lines = content.split('\n')
    table_start = next((i for i, line in enumerate(lines) if '| Game Title' in line), None) + 2
    table_end = next((i for i, line in enumerate(lines) if not line.startswith('|') and i > table_start), len(lines))

    # Adjust widths based on observed table format
    new_entry = f"| [{title}](#{convert_title_to_anchor(title)})".ljust(60) + \
                f"| {formatted_time}".ljust(18) + \
                "|               ".ljust(16) + \
                f"| {tags}".ljust(46) + "|"

    inserted = False
    for i in range(table_start, table_end):
        current_time_str = lines[i].split('|')[2].strip()
        current_time = parse_time(current_time_str)
        if compare_times(formatted_time, current_time):
            lines.insert(i, new_entry)
            inserted = True
            break
    if not inserted:
        lines.insert(table_end, new_entry)

    content = '\n'.join(lines[:table_end + 1])
    content += append_game_detail(title, formatted_time, steam_url, tags)
    thumbnails = run_thumbnail_script()
    content += f"{thumbnails}\n"
    content += '\n'.join(lines[table_end + 1:])

    return content

def append_game_detail(title, formatted_time, steam_url, tags):
    detail_section = f"""

# {title}

- **Steam Page**: [{title}]({steam_url})
- **Total Play Time**: {formatted_time}
- **Will Purchase**: 
- **Type**: {tags}

> 🕹️ **Description**: 
> 
> 👍👎  **Feedback**: 

"""
    return detail_section

def run_thumbnail_script():
    result = subprocess.run(["python", "thumbnail.py"], capture_output=True, text=True)
    return result.stdout.strip()

def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python add.py <steam_url> <time_played> [tags]")
        return

    steam_url = sys.argv[1]
    time_played = sys.argv[2]
    tags = sys.argv[3] if len(sys.argv) == 4 else ""

    formatted_time = format_time_played(time_played)
    title = extract_game_title(steam_url)

    # Set the markdown filename
    markdown_filename = "2025_Feb.md"
    
    if not os.path.exists(markdown_filename):
        print(f"The file {markdown_filename} does not exist.")
        return

    with open(markdown_filename, "r") as file:
        content = file.read()

    content = insert_game_into_table(content, title, formatted_time, steam_url, tags)
    
    with open(markdown_filename, "w") as file:
        file.write(content)

if __name__ == "__main__":
    main()
