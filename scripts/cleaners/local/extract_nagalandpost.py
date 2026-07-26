# MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import os
import re

def clean_content(text):
    # Fix the "City, MON DD (AGENCY): Content" issue
    text = re.sub(r'^([A-Za-z\s/]+, [A-Z]+\s\d+\s\([A-Za-z]+\):)\n\s*', r'\1 ', text)
    # Replace 3 or more newlines with just 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def _extract_nagalandpost_title(soup):
    title_tag = soup.find('h1', class_='tdb-title-text')
    return title_tag.get_text().strip() if title_tag else "N/A"

def _extract_nagalandpost_intro(soup):
    intro_meta = soup.find('meta', attrs={"name": "description"})
    return intro_meta.get('content', '').strip() if intro_meta else ""

def _extract_nagalandpost_date(soup):
    date_meta = soup.find('meta', property='article:published_time')
    return date_meta.get('content', 'N/A') if date_meta else "N/A"

def _extract_nagalandpost_image(soup):
    img_meta = soup.find('meta', property='og:image')
    featured_image = img_meta.get('content', 'N/A') if img_meta else "N/A"
    image_blacklist = ["npmain.png", "cropped-favicon"]
    if any(blacklisted in featured_image for blacklisted in image_blacklist):
        featured_image = "N/A"
    return featured_image

def extract_nagalandpost(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    title = _extract_nagalandpost_title(soup)
    short_intro = _extract_nagalandpost_intro(soup)
    date_str = _extract_nagalandpost_date(soup)
    featured_image = _extract_nagalandpost_image(soup)

    # 5. Extract Content Body
    body_container = soup.find('div', class_='td-post-content')
    if not body_container:
        return "Failed to find content"

    # Extract another_image from inline content before decomposing
    another_image = "N/A"
    img_tag = body_container.find('img')
    if img_tag:
        another_image = img_tag.get('data-src') or img_tag.get('data-lazy-src') or img_tag.get('src', 'N/A')

    # Decompose all figures, inline images, and captions from content
    for tag in body_container.find_all(['figure', 'img', 'figcaption']):
        tag.decompose()

    # Remove Junk
    junk_selectors = [
        '.td-a-rec', 
        '.tdb-post-meta', 
        '.td-post-featured-image',
        '.tdb_single_author',
        '.tdb_single_next_prev',
        '.td-post-sharing-top',
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

    data = {
        "title": title,
        "short_intro": short_intro,
        "date": date_str,
        "featured_image": featured_image,
        "another_image": another_image,
        "content": clean_body
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return "Success"
