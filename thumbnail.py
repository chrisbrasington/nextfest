#!/usr/bin/env python
import os
from PIL import Image
import re

# Step 1: Create thumbnails for images in img/demos if they don't already exist
input_dir = "img/2024_feb"
output_dir = "img/thumbnails"

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

for root, dirs, files in os.walk(input_dir):
    for filename in files:
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            img_path = os.path.join(root, filename)
            thumbnail_path = os.path.join(output_dir, filename)
            
            # Only create the thumbnail if it doesn't already exist
            if not os.path.exists(thumbnail_path):
                img = Image.open(img_path)
                thumbnail = img.copy()
                thumbnail.thumbnail((400, 400))  # You can adjust the size of the thumbnail as needed.
                thumbnail.save(thumbnail_path)
                
                image_folder = os.path.dirname(img_path)
                print(f"[![Thumbnail]({output_dir}/{filename})]({image_folder}/{filename})")


# Step 2: Read README.md and replace image links with thumbnails and full-size hyperlinks
# readme_path = "README.md"

# with open(readme_path, 'r') as f:
#     readme_content = f.read()

# def replace_image_links(match):
#     img_path = match.group(1)
#     thumbnail_path = os.path.join("img/thumbnails", os.path.basename(img_path))
#     replaced_link = f'[![Thumbnail]({thumbnail_path})]({img_path})'
#     return replaced_link

# pattern = r'\!\[.*\]\((img/demos/[^)]+)\)'
# updated_readme_content = re.sub(pattern, replace_image_links, readme_content)

# with open(readme_path, 'w') as f:
#     f.write(updated_readme_content)

# print("Thumbnails created and README.md updated.")
# print("Thumbnails created.")
