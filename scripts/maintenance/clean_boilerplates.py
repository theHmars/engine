import os
import glob
import re

CONTENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'content', 'markdown'))

# Regex to catch the EastMojo boilerplate and variations of it
# It looks for "**Dear Reader," and captures everything up until the closing "**" 
# that follows "Editor-in-Chief" or "eastmojo.com" without backtracking.
BOILERPLATE_REGEX = re.compile(
    r'\*\*Dear Reader,(?:[^*]|\*(?!\*))*(?:Editor-in-Chief|eastmojo\.com)(?:[^*]|\*(?!\*))*\*\*',
    re.IGNORECASE
)

# Also catch the alternative generic support messages
SUPPORT_REGEX = re.compile(
    r'You just read a story that took days to report\. Help us keep our reporters on the ground.*?(?:Support once \(any amount\)|Support us)',
    re.IGNORECASE | re.DOTALL
)

# Catch "Also Read | [Title](URL)" or "Read more: [Title](URL)"
ALSO_READ_REGEX = re.compile(
    r'(?i)^[^*]*(?:\*\*)?(?:Also Read|Read more|Related|Read Also)(?:\*\*)?[\s\|:]*\[[^\]]+\]\(https?://[^\)]+\).*$',
    re.MULTILINE
)

def clean_markdown_files():
    # Search all markdown files in all subdirectories (local, national, global)
    md_files = glob.glob(os.path.join(CONTENT_DIR, '**', '*.md'), recursive=True)
    
    cleaned_count = 0
    
    for filepath in md_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
        # Remove the boilerplate blocks
        new_content = BOILERPLATE_REGEX.sub('', original_content)
        new_content = SUPPORT_REGEX.sub('', new_content)
        new_content = ALSO_READ_REGEX.sub('', new_content)
        
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
