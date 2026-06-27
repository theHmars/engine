# MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import os
import re

def clean_content(text):
    # Fix the common "City, Month Date:" issue (e.g. New Delhi, June 15:)
    text = re.sub(r'^([A-Za-z\s]+, [A-Za-z]+\s\d+:)\n\s*', r'\1 ', text)
    # Replace 3 or more newlines with just 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_shillongtimes(html_path, output_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Extract Title
    title_tag = soup.find('h1', class_='tdb-title-text')
    title = title_tag.get_text().strip() if title_tag else "N/A"

    # 2. Extract Date (Metadata)
    date_meta = soup.find('meta', itemprop='datePublished')
    date_str = date_meta['content'] if date_meta else "N/A"

    # 3. Extract Featured Image
    img_meta = soup.find('meta', property='og:image')
    if not img_meta:
        img_meta = soup.find('meta', itemprop='url', content=re.compile(r'\.(jpg|jpeg|png|webp)'))
    
    featured_image = img_meta['content'] if img_meta else "N/A"
    
    # Blacklist generic TST logo/placeholders
    image_blacklist = ["Tst-logo-2.png", "TST.jpg", "download-4.jpeg"]
    if any(blacklisted in featured_image for blacklisted in image_blacklist):
        featured_image = "N/A"

    # 4. Extract Content Body
    body_container = soup.find('div', class_='td-post-content')
    if not body_container:
        return "Failed to find content"

    # Handle Images within content
    for img in body_container.find_all('img'):
        img_src = img.get('src', '')
        if img_src and not 'addtoany' in img_src and not any(b in img_src for b in image_blacklist):
            placeholder = soup.new_tag("p")
            placeholder.string = f"image link: {img_src}"
            img.replace_with(placeholder)

    # Remove Junk
    junk_selectors = [
        '.td-a-rec', '.tdb-post-meta', '.td-post-featured-image',
        '.tdb_single_author', '.tdb_single_next_prev', '.td-post-sharing-top',
        'script', 'style'
    ]
    for selector in junk_selectors:
        for tag in body_container.select(selector):
            tag.decompose()

    body_text = body_container.get_text(separator='\n')
    clean_body = clean_content(body_text)

    # No short intro for this source, using empty string to keep schema consistent
    short_intro = ""

    data = {
        "title": title,
        "short_intro": short_intro,
        "date": date_str,
        "featured_image": featured_image,
        "content": clean_body
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return "Success"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        print(extract_shillongtimes(sys.argv[1], sys.argv[2]))
    else:
        # Default test
        html_file = f'tmp/{scope}/research/local/shillongtimes/1.html'
        output_file = f'tmp/{scope}/research/local/shillongtimes/1_clean.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(extract_shillongtimes(html_file, output_file))
