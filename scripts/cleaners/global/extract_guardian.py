from bs4 import BeautifulSoup
import json
import re
import os
from urllib.parse import urlparse

def clean_content(text):
    # Strip any residual <br> tags that survived HTML extraction
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    # Replace multiple newlines with exactly two
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def _extract_title(soup):
    title_tag = soup.find('h1')
    if title_tag:
        return title_tag.get_text().strip()
    title_meta = soup.find('meta', property='og:title')
    if title_meta and title_meta.has_attr('content'):
        return title_meta['content']
    return "N/A"

def _extract_date(soup):
    date_meta = soup.find('meta', property='article:published_time')
    if date_meta and date_meta.has_attr('content'):
        return date_meta['content']
    time_tag = soup.find('time')
    if time_tag and time_tag.has_attr('datetime'):
        return time_tag['datetime']
    return "N/A"

def _is_valid_guardian_image(src):
    host = (urlparse(src).hostname or "").lower()
    return host == "guim.co.uk" or host.endswith(".guim.co.uk")

def _process_figure(element, content_parts):
    img = element.find('img')
    if not img:
        return
    src = img.get('src') or img.get('data-src')
    if src and _is_valid_guardian_image(src):
        content_parts.append(f"image link: {src}")

def _extract_body_parts(search_target):
    """Extracts text and image link parts from the cleaned search target."""
    content_parts = []
    for element in search_target.find_all(['p', 'h2', 'h3', 'figure']):
        if element.name == 'figure':
            _process_figure(element, content_parts)
        else:
            text = element.get_text().strip()
            if text:
                content_parts.append(text)
    return content_parts

def extract_guardian(html_path, output_path):
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
    body_container = soup.find('div', id='maincontent') or soup.find('article')
    if not body_container:
        return "Failed to find content"

    # Define selectors for junk to remove
    junk_selectors = [
        'script', 'style', 'nav', 'header', 'footer', 'aside',
        '.dcr-1vetsv0', # Sidebar/Ads
        '.ad-slot-container',
        'gu-island', # Interactive elements
        '.dcr-qxqnsy', # Related topics
        '.content-footer'
    ]

    # Clone container to avoid modifying the original soup
    clean_soup = BeautifulSoup(str(body_container), 'html.parser')
    for selector in junk_selectors:
        for tag in clean_soup.select(selector):
            tag.decompose()

    # In Guardian, the content usually resides in a div with role='main' inside the article
    main_role = clean_soup.find('div', role='main')
    search_target = main_role if main_role else clean_soup

    content_parts = _extract_body_parts(search_target)
    full_body = "\n\n".join(content_parts)
    clean_body = clean_content(full_body)

    data = {
        "title": title,
        "short_intro": "",
        "date": date_str,
        "featured_image": featured_image,
        "content": clean_body
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

    return "Success"
