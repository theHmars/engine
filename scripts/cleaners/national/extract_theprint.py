# NOT MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import re
import os


def clean_content(text):
    # Strip any residual <br> tags that survived HTML extraction
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    # Remove the standard "This report is auto-generated..." disclaimer from The Print
    disclaimer_pattern = r'This report is auto-generated from .* news service\. ThePrint holds no responsibility for its content\.'
    text = re.sub(disclaimer_pattern, '', text, flags=re.IGNORECASE)
    # Remove trailing PTI/Agency tags often found at the end
    text = re.sub(r'PTI[\sA-Z]+$', '', text.strip())
    # Replace multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def _remove_theprint_junk(container):
    junk_selectors = ['script', 'style', '.td-ad-view', '.code-block', 'button', '.ap-m-clip-expand']
    for selector in junk_selectors:
        for tag in container.select(selector):
            tag.decompose()

def _extract_paragraphs(container):
    parts = []
    for p in container.find_all('p'):
        if not p.find('p'):
            text = p.get_text().strip()
            if text and len(text) > 2 and "Show Full Article" not in text:
                parts.append(text)
    return parts

def _extract_subheadings(container):
    parts = []
    for h in container.find_all(['h2', 'h3']):
        text = h.get_text().strip()
        if text:
            parts.append(text)
    return parts

def _extract_clean_paragraphs(container):
    if not container:
        return []
    _remove_theprint_junk(container)
    parts = _extract_paragraphs(container)
    parts.extend(_extract_subheadings(container))
    return parts

def _extract_theprint_title(soup):
    title_tag = soup.find('h1', class_='tdb-title-text')
    if title_tag:
        return title_tag.get_text().strip()
    title_meta = soup.find('meta', property='og:title')
    if title_meta:
        return title_meta.get('content', 'N/A')
    return "N/A"

def _extract_theprint_date(soup):
    time_tag = soup.find('time', class_='entry-date')
    if time_tag:
        return time_tag.get('datetime', 'N/A')
    date_meta = soup.find('meta', property='article:published_time')
    if date_meta:
        return date_meta.get('content', 'N/A')
    return "N/A"

def _extract_theprint_image(soup):
    img_meta = soup.find('meta', property='og:image')
    if img_meta:
        return img_meta.get('content', 'N/A')
    return "N/A"

def extract_theprint(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    title = _extract_theprint_title(soup)
    date_str = _extract_theprint_date(soup)
    featured_image = _extract_theprint_image(soup)

    # 4. Content Body
    # The Print uses 'postexcerpt' for the preview and 'postcontent' for the rest.
    # Horrible HTML: every <p> is nested inside another <p>.
    content_parts = []
    
    pe = soup.find('div', id='postexcerpt')
    pc = soup.find('div', id='postcontent')
    
    if pe or pc:
        content_parts.extend(_extract_clean_paragraphs(pe))
        content_parts.extend(_extract_clean_paragraphs(pc))
    else:
        # Final fallback
        body_container = soup.find('div', class_='td-post-content')
        if body_container:
            content_parts.extend(_extract_clean_paragraphs(body_container))

    if not content_parts:
        return "Failed to find content"

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
