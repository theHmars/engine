import os
import glob
import re

CONTENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'content', 'markdown'))

def remove_eastmojo_boilerplate(text):
    start = text.find("**Dear Reader,")
    if start != -1:
        end = text.find("**", start + 14)
        if end != -1:
            block = text[start:end+2]
            if "Editor-in-Chief" in block or "eastmojo" in block:
                text = text.replace(block, "")
    return text

def remove_support_message(text):
    start = text.find("You just read a story that took days to report.")
    if start != -1:
        end = text.find("Support us", start)
        if end != -1:
            text = text[:start] + text[end + 10:]
        else:
            end = text.find("Support once", start)
            if end != -1:
                eol = text.find("\n", end)
                if eol != -1:
                    text = text[:start] + text[eol:]
    return text

def remove_also_read(text):
    lines = text.splitlines()
    new_lines = []
    keywords = ["also read", "read more", "related", "read also"]
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords) and "[" in line and "](" in line:
            if ("http" + "://") in line or "https://" in line:
                continue
        new_lines.append(line)
    return "\n".join(new_lines)

def clean_markdown_files():
    # Search all markdown files in all subdirectories (local, national, global)
    md_files = glob.glob(os.path.join(CONTENT_DIR, '**', '*.md'), recursive=True)
    
    cleaned_count = 0
    
    for filepath in md_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
        # Remove the boilerplate blocks using safe string matching
        new_content = remove_eastmojo_boilerplate(original_content)
        new_content = remove_support_message(new_content)
        new_content = remove_also_read(new_content)
        
        # Clean up any excessive blank lines left behind (more than 2 newlines)
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)
        
        if new_content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            cleaned_count += 1
            print(f"Cleaned boilerplate from: {os.path.basename(filepath)}")
            
    print(f"\nSuccessfully scrubbed boilerplate from {cleaned_count} articles!")

if __name__ == "__main__":
    clean_markdown_files()
