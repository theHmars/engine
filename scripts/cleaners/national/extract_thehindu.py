# MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import re
import os

def clean_content(text):
    # The Hindu often has "Published - June..." at the bottom if using broad selector
    text = re.sub(r'Published\s+-.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # Remove recurring "Read Comments" text
    text = re.sub(r'Read\s+Comments.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # Remove "Related Topics"
    text = re.sub(r'Related Topics.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # Replace multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_thehindu(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Title
    title = "N/A"
    title_tag = soup.find('h1')
    if title_tag:
        title = title_tag.get_text().strip()
    
    if title == "N/A" or not title:
        title_meta = soup.find('meta', property='og:title') or soup.find('meta', name='title')
        if title_meta:
            title = title_meta.get('content', "N/A")

    # 2. Date
    date_str = "N/A"
    date_tag = soup.find('p', class_='updated-time') or soup.find('div', class_='update-publish-time')
    if date_tag:
        date_str = re.sub(r'\s+', ' ', date_tag.get_text()).strip()
    else:
        date_meta = soup.find('meta', property='article:published_time') or soup.find('meta', name='publish-date')
        if date_meta:
            date_str = date_meta.get('content', "N/A")

    # Extract Short Intro
    intro_tag = soup.find('h2', class_='sub-title')
    short_intro = intro_tag.get_text().strip() if intro_tag else ""

    # 3. Featured Image
    img_meta = soup.find('meta', property='og:image')
    featured_image = img_meta['content'] if img_meta else "N/A"
    
    # Check for default OG images
    if "og-image.png" in featured_image:
        featured_image = "N/A"

    # 4. Content Body
    body_container = soup.find('div', id=re.compile(r'content-body-')) or soup.find('div', class_='articlebodycontent')
    
    if not body_container:
        # Fallback to schemaDiv if id search fails
        body_container = soup.find('div', class_='schemaDiv')

    if not body_container:
        return "Failed to find content"

    # Decompose junk
    junk_selectors = [
        'script', 'style', '.articleblock-container', '.update-publish-time',
        '.comments-shares', 'button', '.author', '.related-topics-list'
    ]
    for selector in junk_selectors:
        for tag in body_container.select(selector):
            tag.decompose()

    # Handle images in content
    for img in body_container.find_all('img'):
        src = img.get('src') or img.get('data-src-template') or img.get('data-src')
        if src:
            p = soup.new_tag("p")
            p.string = f"image link: {src}"
            img.replace_with(p)

    body_text = body_container.get_text(separator='\n')
    clean_body = clean_content(body_text)

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
        print(extract_thehindu(sys.argv[1], sys.argv[2]))
    else:
        os.makedirs(f'tmp/{scope}/research/thehindu', exist_ok=True)
        print(extract_thehindu(f'tmp/{scope}/raw.html', f'tmp/{scope}/research/thehindu/test_clean.json'))
