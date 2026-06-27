# MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

def clean_content(text):
    # Fix the common "City:\n Content" issue at the start of articles
    text = re.sub(r'^([A-Za-z\s]+:)\n\s*', r'\1 ', text)
    # Replace 3 or more newlines with just 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_eastmojo(html_path, output_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Extract Title
    title_tag = soup.find('h1', class_='entry-title')
    title = title_tag.get_text().strip() if title_tag else "N/A"

    # 2. Extract Short Intro
    intro_tag = soup.find('div', class_='newspack-post-subtitle')
    short_intro = intro_tag.get_text().strip() if intro_tag else "N/A"

    # 3. Extract Date (from meta)
    date_meta = soup.find('meta', property='article:published_time')
    date_str = date_meta['content'] if date_meta else "N/A"
    
    # 4. Extract Main Image
    featured_img_meta = soup.find('meta', property='og:image')
    featured_image = featured_img_meta['content'] if featured_img_meta else "N/A"

    # 5. Extract Content Body
    body_container = soup.find('div', class_='entry-content')
    if not body_container:
        return "Failed to find content"

    # Handle Images within content BEFORE decomposing
    # We replace image tags with a placeholder
    for figure in body_container.find_all(['figure', 'img']):
        # If it's a small icon or share image, skip
        if figure.name == 'img' and (not figure.get('src') or 'addtoany' in figure.get('src')):
            continue
        
        # Get img src
        img_src = ""
        if figure.name == 'img':
            img_src = figure.get('src', '')
        else:
            img = figure.find('img')
            if img:
                img_src = img.get('src', '')
        
        if img_src:
            placeholder = soup.new_tag("p")
            placeholder.string = f"image link: {img_src}"
            figure.replace_with(placeholder)

    # Remove Junk
    junk_selectors = [
        '.addtoany_share_save_container', 
        '#jp-relatedposts', 
        '.newspack_global_ad', 
        '.wp-block-buttons',
        'aside.emm-carousel',
        'script', 'style'
    ]
    for selector in junk_selectors:
        for tag in body_container.select(selector):
            tag.decompose()

    # Remove "Dear Reader" and "Premium" blocks
    for col in body_container.find_all('div', class_='wp-block-columns'):
        if "Dear Reader" in col.get_text():
            col.decompose()

    # Remove "Also Read" and trailing promotional text
    for p in body_container.find_all('p'):
        text = p.get_text().strip()
        if text.startswith("Also Read") or text.startswith("2000+ readers have backed us") or text == "|":
            p.decompose()

    body_text = body_container.get_text(separator='\n')

    data = {
        "title": title,
        "short_intro": short_intro,
        "date": date_str,
        "featured_image": featured_image,
        "content": clean_content(body_text)
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return "Success"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        print(extract_eastmojo(sys.argv[1], sys.argv[2]))
    else:
        # Default test
        html_file = f'tmp/{scope}/research/local/eastmojo/1.html'
        output_file = f'tmp/{scope}/research/local/eastmojo/1_clean.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(extract_eastmojo(html_file, output_file))
