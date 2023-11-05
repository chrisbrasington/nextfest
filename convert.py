import re

# Function to replace image links
def replace_image_links(match):
    image_name = match.group(1)
    return f"![](img/demos/{image_name.replace(' ', '%20')})"

# Input file
input_file = "demos.md"
output_file = "demos_updated.md"

# Regular expression to match image links
pattern = r"!\[\[([^\]]+)\]\]"

with open(input_file, "r") as f:
    content = f.read()

# Use re.sub() to find and replace image links
updated_content = re.sub(pattern, replace_image_links, content)

# Write the updated content to the output file
with open(output_file, "w") as f:
    f.write(updated_content)

print(f"Image links replaced and saved to {output_file}")

