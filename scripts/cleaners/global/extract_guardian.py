from bs4 import BeautifulSoup
import json
import re
import os

def clean_content(text):
    # Replace multiple newlines with exactly two
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_guardian(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Title
    title = "N/A"
    title_tag = soup.find('h1')
    if title_tag:
        title = title_tag.get_text().strip()
    else:
        title_meta = soup.find('meta', property='og:title')
        if title_meta:
            title = title_meta['content']

    # 2. Date
    date_str = "N/A"
    date_meta = soup.find('meta', property='article:published_time')
    if date_meta:
        date_str = date_meta['content']
    else:
        # Fallback to time tag
        time_tag = soup.find('time')
        if time_tag and time_tag.has_attr('datetime'):
            date_str = time_tag['datetime']

    # 3. Featured Image
    img_meta = soup.find('meta', property='og:image')
    featured_image = img_meta['content'] if img_meta else "N/A"

    # 4. Content Body
    # Guardian DCR usually puts content in an 'article' tag or 'div' with id 'maincontent'
    body_container = soup.find('div', id='maincontent') or soup.find('article')
    
    if not body_container:
        return "Failed to find content"

    # Identify the specific content blocks.
    # In DCR, paragraphs usually have a class starting with 'dcr-'
    # but they are direct children of the body container or inside a wrapper.
    content_parts = []
    
    # Target elements: paragraphs, subheadings, and images
    # We want to exclude the header, meta info, and footer/sidebar
    
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

    # Find all paragraphs and images
    # In Guardian, the content usually resides in a div with role='main' inside the article
    main_role = clean_soup.find('div', role='main')
    search_target = main_role if main_role else clean_soup

    # Extract text and image placeholders
    for element in search_target.find_all(['p', 'h2', 'h3', 'figure']):
        if element.name == 'figure':
            # Look for image and caption
            img = element.find('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src:
                    # Filter out tiny icons or tracking pixels
                    if 'guim.co.uk' in src:
                        content_parts.append(f"image link: {src}")
        else:
            text = element.get_text().strip()
            if text:
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
        print(extract_guardian(sys.argv[1], sys.argv[2]))
    else:
        # Default test case for research
        html_file = f'tmp/{scope}/research/international/guardian/1.html'
        output_file = f'tmp/{scope}/research/international/guardian/1_clean.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(extract_guardian(html_file, output_file))
