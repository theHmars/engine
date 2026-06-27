# MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import re
import os


def clean_content(text):
    # Remove multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Sometimes there are "Click here to read" or similar promotional texts
    text = re.sub(r'Click here for more.*', '', text, flags=re.IGNORECASE)
    return text.strip()

def extract_indianexpress(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Title
    title = "N/A"
    title_tag = soup.find('h1', class_='native_story_title')
    if title_tag:
        title = title_tag.get_text().strip()
    else:
        title_meta = soup.find('meta', property='og:title')
        if title_meta:
            title = title_meta['content']

    # 2. Date
    date_str = "N/A"
    date_meta = soup.find('meta', property='article:published_time') or soup.find('meta', itemprop='datePublished')
    if date_meta:
        date_str = date_meta['content']

    # 3. Featured Image
    img_meta = soup.find('meta', property='og:image')
    featured_image = img_meta['content'] if img_meta else "N/A"

    # 4. Content Body
    body_container = soup.find('div', id='pcl-full-content') or soup.find('div', class_='story_details')

    if not body_container:
        return "Failed to find content"

    content_parts = []
    
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

    for element in clean_soup.find_all(['p', 'h2', 'h3', 'img']):
        if element.name == 'img':
            src = element.get('src') or element.get('data-src')
            if src and 'images.indianexpress.com' in src:
                # Avoid tiny icons
                if not any(x in src.lower() for x in ['logo', 'icon', '150x150', '96x96', 'avatar']):
                    content_parts.append(f"image link: {src}")
        else:
            text = element.get_text().strip()
            if text and len(text) > 2:
                content_parts.append(text)

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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        print(extract_indianexpress(sys.argv[1], sys.argv[2]))
    else:
        # Default test case for research
        html_file = f'tmp/{scope}/research/national/indianexpress/1.html'
        output_file = f'tmp/{scope}/research/national/indianexpress/1_clean.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(extract_indianexpress(html_file, output_file))
