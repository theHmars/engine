# MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import re
import os
from urllib.parse import urlparse


def clean_content(text):
    # Strip any residual <br> tags that survived HTML extraction
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    # Remove multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Sometimes there are "Click here to read" or similar promotional texts
    text = re.sub(r'Click here for more.*', '', text, flags=re.IGNORECASE)
    return text.strip()

def is_allowed_image_host(src):
    try:
        host = urlparse(src).hostname
    except Exception:
        return False
    if not host:
        return False
    host = host.lower()
    return host == 'images.indianexpress.com' or host.endswith('.images.indianexpress.com')

def _is_icon_image(src):
    return any(x in src.lower() for x in ['logo', 'icon', '150x150', '96x96', 'avatar'])

def _extract_title(soup):
    title_tag = soup.find('h1', class_='native_story_title')
    if title_tag:
        return title_tag.get_text().strip()
    title_meta = soup.find('meta', property='og:title')
    if title_meta and title_meta.has_attr('content'):
        return title_meta['content']
    return "N/A"

def _extract_date(soup):
    date_meta = soup.find('meta', property='article:published_time') or soup.find('meta', itemprop='datePublished')
    if date_meta and date_meta.has_attr('content'):
        return date_meta['content']
    return "N/A"

def _extract_body_parts(clean_soup):
    """Extracts text and valid image links from the cleaned soup."""
    content_parts = []
    for element in clean_soup.find_all(['p', 'h2', 'h3', 'img']):
        if element.name == 'img':
            src = element.get('src') or element.get('data-src')
            if src and is_allowed_image_host(src) and not _is_icon_image(src):
                content_parts.append(f"image link: {src}")
        else:
            text = element.get_text().strip()
            if text and len(text) > 2:
                content_parts.append(text)
    return content_parts

def extract_indianexpress(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    title = _extract_title(soup)
    date_str = _extract_date(soup)

    img_meta = soup.find('meta', property='og:image')
    featured_image = "N/A"
    if img_meta:
        featured_image = img_meta.get('content', 'N/A')

    # 4. Content Body
    body_container = soup.find('div', id='pcl-full-content') or soup.find('div', class_='story_details')
    if not body_container:
        return "Failed to find content"

    # Junk removal
    junk_selectors = [
        'script', 'style', 'nav', 'header', 'footer', 'aside',
        '.app-ad', '.custom-ad', '.ie-ad', '.ad-box', '.ad-container',
        '.also-read', '.read-more', '.related-articles',
        '.newsletter-widget', '.author-widget'
    ]
    clean_soup = BeautifulSoup(str(body_container), 'html.parser')
    for selector in junk_selectors:
        for tag in clean_soup.select(selector):
            tag.decompose()

    content_parts = _extract_body_parts(clean_soup)
    full_body = "\n\n".join(content_parts)
    clean_body = clean_content(full_body)

    # Extract Short Intro
    intro_tag = soup.find('h2', class_='synopsis') or soup.find('h2', itemprop='description')
    short_intro = intro_tag.get_text().strip() if intro_tag else ""

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
