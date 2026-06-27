# NOT MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import re
import os

def clean_content(text):
    # Remove common UI noise
    text = re.sub(r'Removed from bookmarks', '', text)
    text = re.sub(r'I would like to be emailed about offers.*Privacy notice', '', text, flags=re.DOTALL)
    # Replace multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_independent(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Title
    title = "N/A"
    title_meta = soup.find('meta', property='og:title') or soup.find('meta', name='twitter:title')
    if title_meta:
        title = title_meta['content']
    else:
        title_tag = soup.find('h1')
        if title_tag:
            title = title_tag.get_text().strip()

    # 2. Date
    date_str = "N/A"
    date_meta = soup.find('meta', property='article:published_time') or soup.find('meta', name='date')
    if date_meta:
        date_str = date_meta['content']
    else:
        time_tag = soup.find('time')
        if time_tag and time_tag.has_attr('datetime'):
            date_str = time_tag['datetime']

    # 3. Featured Image
    img_meta = soup.find('meta', property='og:image') or soup.find('meta', name='twitter:image')
    featured_image = img_meta['content'] if img_meta else "N/A"

    # 4. Content Body
    # The Independent often uses an 'article' tag or a div with id='main'
    # We found id='main' contains the core paragraphs
    body_container = soup.find('div', id='main') or soup.find('article')
    
    if not body_container:
        return "Failed to find content"

    content_parts = []
    
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

    # Extract all relevant text blocks
    # We prioritize 'p' tags inside the main container
    for element in clean_soup.find_all(['p', 'h2', 'h3', 'figure']):
        # Skip some known noisy paragraphs
        text = element.get_text().strip()
        if not text: continue
        
        # Filter out UI strings
        if any(noise in text for noise in ['Removed from bookmarks', 'Read our Privacy notice', 'Sign up to our']):
            continue

        if element.name == 'figure':
            img = element.find('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src and 'static.independent.co.uk' in src:
                    content_parts.append(f"image link: {src}")
        else:
            content_parts.append(text)

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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        print(extract_independent(sys.argv[1], sys.argv[2]))
    else:
        # Default test for research
        html_file = f'tmp/{scope}/research/international/independent/1.html'
        output_file = f'tmp/{scope}/research/international/independent/1_clean.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(extract_independent(html_file, output_file))
