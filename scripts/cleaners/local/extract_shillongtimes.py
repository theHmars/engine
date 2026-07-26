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

def _extract_shillongtimes_title(soup):
    title_tag = soup.find('h1', class_='tdb-title-text')
    return title_tag.get_text().strip() if title_tag else "N/A"

def _extract_shillongtimes_date(soup):
    date_meta = soup.find('meta', itemprop='datePublished')
    return date_meta.get('content', 'N/A') if date_meta else "N/A"

def _extract_shillongtimes_image(soup):
    img_meta = soup.find('meta', property='og:image')
    if not img_meta:
        img_meta = soup.find('meta', itemprop='url', content=re.compile(r'\.(jpg|jpeg|png|webp)'))
    featured_image = img_meta.get('content', 'N/A') if img_meta else "N/A"
    
    # Blacklist generic TST logo/placeholders
    image_blacklist = ["Tst-logo-2.png", "TST.jpg", "download-4.jpeg"]
    if any(blacklisted in featured_image for blacklisted in image_blacklist):
        featured_image = "N/A"
    return featured_image

def extract_shillongtimes(html_path, output_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    title = _extract_shillongtimes_title(soup)
    date_str = _extract_shillongtimes_date(soup)
    featured_image = _extract_shillongtimes_image(soup)

    # 4. Extract Content Body
    body_container = soup.find('div', class_='td-post-content')
    if not body_container:
        return "Failed to find content"

    # Handle Images within content
    for img in body_container.find_all('img'):
        img_src = img.get('src', '')
        if img_src and 'addtoany' not in img_src and not any(b in img_src for b in image_blacklist):
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

    # Strip <br> tags before text extraction — get_text() does not remove inline tags
    for br in body_container.find_all('br'):
        br.replace_with(' ')

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
