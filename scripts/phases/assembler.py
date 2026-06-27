import json
import os
from datetime import datetime
from utils.common import slugify, ensure_dirs

# Mapping of regions to their default fallback images on EastMojo/TheHmars
DEFAULT_IMAGES = {
    "Arunachal Pradesh": "/assets/fallback.webp",
    "Assam": "/assets/fallback.webp",
    "Manipur": "/assets/fallback.webp",
    "Meghalaya": "/assets/fallback.webp",
    "Mizoram": "/assets/fallback.webp",
    "Nagaland": "/assets/fallback.webp",
    "Sikkim": "/assets/fallback.webp",
    "Tripura": "/assets/fallback.webp",
    "N/A": "/assets/fallback.webp"
}

def load_ignored_images():
    """Loads list of image paths to ignore from data/ignore_image_paths.txt."""
    ignored = set()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    from utils.common import get_scope
    scope = get_scope()
    ignore_path = os.path.join(root_dir, "data/ignore_image_paths.txt")
    if os.path.exists(ignore_path):
        try:
            with open(ignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignored.add(line)
        except Exception as e:
            print(f"  [!] Error loading ignored images: {e}")
    return ignored

IGNORED_IMAGES = load_ignored_images()

def generate_yaml(article, date_iso):
    """Programmatically constructs the YAML frontmatter to avoid AI syntax errors."""
    
    category = article.get('category', 'Local')
    is_local = category not in ["National", "International", "Global"]
    if not is_local:
        region = "N/A"
    else:
        region = article.get('region', 'N/A')
        
    # Handle the image fallback logic
    img_url = article.get('featured_image')
    if img_url in IGNORED_IMAGES:
        print(f"    [-] Image '{img_url}' matches ignore list. Replacing with fallback.")
        img_url = None
        
    if not img_url or img_url in ["N/A", "null", "None", ""]:
        img_url = DEFAULT_IMAGES.get(region, DEFAULT_IMAGES["N/A"])
        
    # Clean description for YAML (escape quotes)
    desc = article.get('description', '').replace('"', "'").strip()
    title = article.get('title', '').replace('"', "'").strip()
    
    yaml = "---\n"
    yaml += f'title: "{title}"\n'
    yaml += f'description: "{desc}"\n'
    yaml += f"date: '{date_iso}'\n"
    yaml += f"category: {category}\n"
    if is_local:
        yaml += f"region: {region}\n"
    yaml += f"majorTag: {article.get('majorTag', 'Politics')}\n"
    yaml += "language: en\n"
    yaml += f"image: {img_url}\n"
    yaml += "isAgentGenerated: true\n"
    yaml += "isVerified: false\n"
    yaml += "---\n\n"
    
    return yaml

def run_assembler():
    print(">>> Starting Task 6: The Assembler")
    
    input_path = f'tmp/{scope}/validated_articles.json'
    output_dir = 'data/processed/ready_for_sync'
    
    if not os.path.exists(input_path):
        print("[!] No validated articles found.")
        return
        
    os.makedirs(output_dir, exist_ok=True)
    
    with open(input_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)
        
    if not articles:
        print(">>> Article list is empty. Exiting.")
        return

    now = datetime.utcnow()
    date_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    date_prefix = now.strftime('%Y-%m-%d')
    
    success_count = 0
    
    for art in articles:
        try:
            # 1. Generate Filename (e.g. 2026-06-15-this-is-the-title.md)
            slug = slugify(art['title'])
            filename = f"{date_prefix}-{slug}.md"
            filepath = os.path.join(output_dir, filename)
            
            # 2. Generate YAML
            yaml_header = generate_yaml(art, date_iso)
            
            # 3. Assemble File
            final_content = yaml_header + art.get('content', '')
            
            # 4. Save
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(final_content)
                
            print(f"  [+] Assembled: {filename}")
            success_count += 1
            
        except Exception as e:
            print(f"  [!] Failed to assemble article '{art.get('title')}': {e}")
            
    print(f">>> Assembler Complete. {success_count}/{len(articles)} files ready for sync.")

if __name__ == "__main__":
    run_assembler()
