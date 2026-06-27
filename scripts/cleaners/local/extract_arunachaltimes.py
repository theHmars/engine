# MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import os
import re

def clean_content(text):
    # Fix the "City, DD Mon:\n Content" issue
    text = re.sub(r'^([A-Z\s]+, \d+\s[A-Za-z]+:)\n\s*', r'\1 ', text)
    # Replace 3 or more newlines with just 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_arunachaltimes(html_path, output_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Extract Title
    title_tag = soup.find('h1', class_='entry-title')
    title = title_tag.get_text().strip() if title_tag else "N/A"

    # 2. Extract Date (Metadata)
    date_meta = soup.find('meta', itemprop='datePublished')
    date_str = date_meta['content'] if date_meta else "N/A"

    # 3. Extract Featured Image
    img_meta = soup.find('meta', property='og:image')
    if not img_meta:
        # Look for the itemprop="url" that ends in common image extensions
        img_meta = soup.find('meta', itemprop='url', content=re.compile(r'\.(jpg|jpeg|png|webp)'))
    
    featured_image = img_meta['content'] if img_meta else "N/A"
    
    # Blacklist generic TST logo/placeholders
    image_blacklist = [
        "bannerlogo.jpg", 
        "td_meta_replacement.png"
    ]
    if any(blacklisted in featured_image for blacklisted in image_blacklist):
        featured_image = "N/A"

    # 4. Extract Content Body
    body_container = soup.find('div', class_='td-post-content')
    if not body_container:
        return "Failed to find content"

    # Handle Images within content
    for img in body_container.find_all('img'):
        img_src = img.get('src', '')
        if img_src and not 'social' in img_src and not 'addtoany' in img_src:
            placeholder = soup.new_tag("p")
            placeholder.string = f"image link: {img_src}"
            img.replace_with(placeholder)

    # Remove Junk
    junk_selectors = [
        '.td-post-sharing-top', 
        '.td-post-sharing-bottom', 
        '.td-post-next-prev',
        '.sharedaddy',
        '.jp-relatedposts',
        'script', 'style'
    ]
    for selector in junk_selectors:
        for tag in body_container.select(selector):
            tag.decompose()

    body_text = body_container.get_text(separator='\n')
    clean_body = clean_content(body_text)

    # No dedicated subtitle for this source
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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        print(extract_arunachaltimes(sys.argv[1], sys.argv[2]))
    else:
        # Default test
        html_file = f'tmp/{scope}/research/local/arunachal/1.html'
        output_file = f'tmp/{scope}/research/local/arunachal/1_clean.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(extract_arunachaltimes(html_file, output_file))
