# NOT MANUALLY VERIFIED
from bs4 import BeautifulSoup
import json
import re
import os


def clean_content(text):
    # Remove the standard "This report is auto-generated..." disclaimer from The Print
    disclaimer_pattern = r'This report is auto-generated from .* news service\. ThePrint holds no responsibility for its content\.'
    text = re.sub(disclaimer_pattern, '', text, flags=re.IGNORECASE)
    
    # Remove trailing PTI/Agency tags often found at the end
    text = re.sub(r'PTI\s+[A-Z\s]+$', '', text.strip())
    
    # Replace multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_theprint(html_path, output_path):
    if not os.path.exists(html_path):
        return f"Error: {html_path} not found"

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    # 1. Title
    title = "N/A"
    title_tag = soup.find('h1', class_='tdb-title-text')
    if title_tag:
        title = title_tag.get_text().strip()
    else:
        title_meta = soup.find('meta', property='og:title')
        if title_meta:
            title = title_meta['content']

    # 2. Date
    date_str = "N/A"
    time_tag = soup.find('time', class_='entry-date')
    if time_tag and time_tag.has_attr('datetime'):
        date_str = time_tag['datetime']
    else:
        date_meta = soup.find('meta', property='article:published_time')
        if date_meta:
            date_str = date_meta['content']

    # 3. Featured Image
    img_meta = soup.find('meta', property='og:image')
    featured_image = img_meta['content'] if img_meta else "N/A"

    # 4. Content Body
    # The Print uses 'postexcerpt' for the preview and 'postcontent' for the rest.
    # Horrible HTML: every <p> is nested inside another <p>.
    content_parts = []
    
    def extract_clean_paragraphs(container):
        parts = []
        if container:
            # Junk removal from container
            junk_selectors = ['script', 'style', '.td-ad-view', '.code-block', 'button', '.ap-m-clip-expand']
            for selector in junk_selectors:
                for tag in container.select(selector):
                    tag.decompose()
            
            # Find all paragraphs, but only keep the innermost ones to avoid nesting duplication
            for p in container.find_all('p'):
                if not p.find('p'):
                    text = p.get_text().strip()
                    if text and len(text) > 2 and "Show Full Article" not in text:
                        parts.append(text)
            
            # Also handle subheadings
            for h in container.find_all(['h2', 'h3']):
                text = h.get_text().strip()
                if text:
                    parts.append(text)
        return parts

    pe = soup.find('div', id='postexcerpt')
    pc = soup.find('div', id='postcontent')
    
    if pe or pc:
        content_parts.extend(extract_clean_paragraphs(pe))
        content_parts.extend(extract_clean_paragraphs(pc))
    else:
        # Final fallback
        body_container = soup.find('div', class_='td-post-content')
        if body_container:
            content_parts.extend(extract_clean_paragraphs(body_container))

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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        print(extract_theprint(sys.argv[1], sys.argv[2]))
    else:
        # Default test case for research
        html_file = f'tmp/{scope}/research/national/theprint/1.html'
        output_file = f'tmp/{scope}/research/national/theprint/1_clean.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        print(extract_theprint(html_file, output_file))
