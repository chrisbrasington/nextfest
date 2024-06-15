import sys
import re
import os

def format_time_played(time_played):
    # Interpret time with or without decimals correctly
    if '.' in time_played:
        hours = float(time_played)
        return f"{hours:.1f} hours" if hours != int(hours) else f"{int(hours)} hours"
    else:
        minutes = int(time_played)
        return f"{minutes} minutes"

def extract_game_title(url):
    # Extract game title from the URL
    match = re.search(r'/app/\d+/(.*)/', url)
    return match.group(1).replace('_', ' ') if match else "Unknown Game"

def convert_title_to_anchor(title):
    # Convert the game title to an anchor
    return title.lower().replace(' ', '-').replace('\'', '')

def insert_game_into_table(content, title, formatted_time):
    # Insert the game into the sorted table
    lines = content.split('\n')
    table_start = next((i for i, line in enumerate(lines) if '| Game Title' in line), None) + 2
    table_end = next((i for i, line in enumerate(lines) if not line.startswith('|') and i > table_start), len(lines))
    
    new_entry = f"| [{title}](#{convert_title_to_anchor(title)}) | {formatted_time} |  | #adventure |"
    
    # Find the correct position to insert
    for i in range(table_start, table_end):
        current_time_str = lines[i].split('|')[2].strip()
        current_time = parse_time(current_time_str)
        if compare_times(formatted_time, current_time):
            lines.insert(i, new_entry)
            break
    else:
        lines.insert(table_end, new_entry)
    
    return '\n'.join(lines)

def parse_time(time_str):
    time_str = time_str.replace('+','')

    # Parse time string to comparable format
    if 'hours' in time_str:
        return float(time_str.replace(' hours', ''))
    elif 'minutes' in time_str:
        return int(time_str.replace(' minutes', '')) / 60
    return 0

def compare_times(new_time_str, current_time):
    # Compare new time with the current time
    new_time = parse_time(new_time_str)
    return new_time > current_time

def append_game_detail(content, title, url, formatted_time):
    # Append game detail section
    detail_section = f"""
# {title}

- **Steam Page**: [{title}]({url})
- **Total Play Time**: {formatted_time}
- **Will Purchase**: 
- **Type**: #adventure

> 🕹️ **Description**: 
>
> 👍👎  **Feedback**: 
"""
    return content + detail_section

def main():
    if len(sys.argv) != 3:
        print("Usage: python add.py <steam_url> <time_played>")
        return

    steam_url = sys.argv[1]
    time_played = sys.argv[2]
    
    formatted_time = format_time_played(time_played)
    title = extract_game_title(steam_url)
    
    if not os.path.exists("2024_June.md"):
        print("The file 2024_June.md does not exist.")
        return

    with open("2024_June.md", "r") as file:
        content = file.read()

    content = insert_game_into_table(content, title, formatted_time)
    content = append_game_detail(content, title, steam_url, formatted_time)
    
    with open("2024_June.md", "w") as file:
        file.write(content)

if __name__ == "__main__":
    main()
