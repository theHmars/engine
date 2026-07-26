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

def _extract_arunachal_title(soup):
    title_tag = soup.find('h1', class_='entry-title')
    return title_tag.get_text().strip() if title_tag else "N/A"

def _extract_arunachal_date(soup):
    date_meta = soup.find('meta', itemprop='datePublished')
    date_str = "N/A"
    if date_meta:
        date_str = date_meta.get('content', 'N/A')
    return date_str

def _extract_arunachal_image(soup):
    img_meta = soup.find('meta', property='og:image')
    if not img_meta:
        img_meta = soup.find('meta', itemprop='url', content=re.compile(r'\.(jpg|jpeg|png|webp)'))
    
    featured_image = "N/A"
    if img_meta:
        featured_image = img_meta.get('content', 'N/A')
    
    image_blacklist = [
        "bannerlogo.jpg", 
        "td_meta_replacement.png"
    ]
    if any(blacklisted in featured_image for blacklisted in image_blacklist):
        featured_image = "N/A"
    return featured_image

def extract_arunachaltimes(html_path, output_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    title = _extract_arunachal_title(soup)
    date_str = _extract_arunachal_date(soup)
    featured_image = _extract_arunachal_image(soup)

    # 4. Extract Content Body
    body_container = soup.find('div', class_='td-post-content')
    if not body_container:
        return "Failed to find content"

    # Handle Images within content
    for img in body_container.find_all('img'):
        img_src = img.get('src', '')
        if img_src and 'social' not in img_src and 'addtoany' not in img_src:
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

    # Strip <br> tags before text extraction — get_text() does not remove inline tags
    for br in body_container.find_all('br'):
        br.replace_with(' ')

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
