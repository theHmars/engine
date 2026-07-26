# NOT MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import re
import os
from urllib.parse import urlparse

def clean_content(text):
    # Strip any residual <br> tags that survived HTML extraction
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    # Remove common UI noise
    text = text.replace('Removed from bookmarks', '')
    text = re.sub(r'I would like to be emailed about offers.*Privacy notice', '', text, flags=re.DOTALL)
    # Replace multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def _extract_title(soup):
    title_meta = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'twitter:title'})
    if title_meta:
        return title_meta['content']
    title_tag = soup.find('h1')
    if title_tag:
        return title_tag.get_text().strip()
    return "N/A"

def _extract_date(soup):
    date_meta = soup.find('meta', property='article:published_time') or soup.find('meta', attrs={'name': 'date'})
    if date_meta:
        return date_meta['content']
    time_tag = soup.find('time')
    if time_tag and time_tag.has_attr('datetime'):
        return time_tag['datetime']
    return "N/A"

def _extract_featured_image(soup):
    img_meta = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
    return img_meta['content'] if img_meta else "N/A"

UI_NOISE = ['Removed from bookmarks', 'Read our Privacy notice', 'Sign up to our']

def _is_noisy_element(text):
    return any(noise in text for noise in UI_NOISE)

def _is_valid_independent_image(src):
    hostname = urlparse(src).hostname
    return hostname and hostname.lower() == 'static.independent.co.uk'

def _process_independent_figure(element, content_parts):
    img = element.find('img')
    if not img:
        return
    src = img.get('src') or img.get('data-src')
    if src and _is_valid_independent_image(src):
        content_parts.append(f"image link: {src}")

def _extract_body_parts(clean_soup):
    """Extracts text and image link parts from the cleaned soup."""
    content_parts = []
    for element in clean_soup.find_all(['p', 'h2', 'h3', 'figure']):
        text = element.get_text().strip()
        if not text or _is_noisy_element(text):
            continue
        if element.name == 'figure':
            _process_independent_figure(element, content_parts)
        else:
            content_parts.append(text)
    return content_parts

def extract_independent(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    title = _extract_title(soup)
    date_str = _extract_date(soup)
    featured_image = _extract_featured_image(soup)

    # 4. Content Body
    body_container = soup.find('div', id='main') or soup.find('article')
    if not body_container:
        return "Failed to find content"

    # Junk removal
    junk_selectors = [
        'script', 'style', 'nav', 'header', 'footer', 'aside',
        '.ad-slot-container', '.sc-1rhc7wo', # Sidebar/Ads
        '.eu0wx3a3', # Comments
        '.e1218mwn0', # Share buttons
        '.e18xlpyd0', # Audio/Speech widget
        'form', # Search
        '#js-globals',
        '#piano-container'
    ]
    clean_soup = BeautifulSoup(str(body_container), 'html.parser')
    for selector in junk_selectors:
        for tag in clean_soup.select(selector):
            tag.decompose()

    content_parts = _extract_body_parts(clean_soup)
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
