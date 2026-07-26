import os
import re

FALLBACK_IMAGE = "/assets/fallback.webp"

# Mapping of regions to their default fallback images on EastMojo/TheHmars
DEFAULT_IMAGES = {
    "Arunachal Pradesh": FALLBACK_IMAGE,
    "Assam": FALLBACK_IMAGE,
    "Manipur": FALLBACK_IMAGE,
    "Meghalaya": FALLBACK_IMAGE,
    "Mizoram": FALLBACK_IMAGE,
    "Nagaland": FALLBACK_IMAGE,
    "Sikkim": FALLBACK_IMAGE,
    "Tripura": FALLBACK_IMAGE,
    "N/A": FALLBACK_IMAGE
}

def load_ignored_images():
    """Loads list of image paths to ignore from data/ignore_image_paths.txt."""
    ignored = set()
    from utils.common import get_state_dir
    ignore_path = os.path.join(get_state_dir(), "data/ignore_image_paths.txt")
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


_ABBR_PATTERN_1 = re.compile(
    r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|No|St|Rs|Lt|Col|Gen|Sgt|Pvt|Capt|Maj|Brig|Insp)\.'
)
_ABBR_PATTERN_2 = re.compile(
    r'\b(vs|etc|i\.e|e\.g|km|kg|sq|Mt|ft)\.'
)
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z"])')
_SENTENCES_PER_PARA = 3


def ensure_paragraphs(content: str) -> str:
    """
    Safety-net paragraphing function.

    If the content already has proper paragraph breaks (two or more consecutive
    newlines), it is returned unchanged. Otherwise the content is split into
    sentences and grouped into paragraphs of _SENTENCES_PER_PARA sentences each.

    This runs as the final step in the assembler before content is written to
    disk, acting as a catch-all for cases where the LLM ignored the paragraph
    instruction or the cleaner produced a flat block of text.
    """
    if not content or not content.strip():
        return content

    # Already has paragraph breaks — leave it alone
    if '\n\n' in content.strip():
        return content

    # Protect common abbreviations so they are not treated as sentence endings
    protected = _ABBR_PATTERN_1.sub(lambda m: m.group(0).replace('.', '__DOT__'), content)
    protected = _ABBR_PATTERN_2.sub(lambda m: m.group(0).replace('.', '__DOT__'), protected)

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(protected.strip()) if s.strip()]

    # Restore abbreviation dots
    sentences = [s.replace('__DOT__', '.') for s in sentences]

    if len(sentences) <= 1:
        # Cannot split — return as-is, at least it is clean
        return content

    paragraphs = []
    for i in range(0, len(sentences), _SENTENCES_PER_PARA):
        chunk = sentences[i:i + _SENTENCES_PER_PARA]
        paragraphs.append(' '.join(chunk))

    return '\n\n'.join(paragraphs) + '\n'



