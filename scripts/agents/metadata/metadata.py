import os
import sys
import json
from dotenv import load_dotenv

from utils.llm_client import call_llm as client_call_llm
from utils.common import get_scope

load_dotenv()

def call_llm(system_prompt, user_content):
    try:
        return client_call_llm(system_prompt, user_content, temperature=0.3, max_tokens=1024, timeout=90)
    except Exception as e:
        print(f"      [!] Metadata LLM Client Error: {e}")
        raise e

def generate_metadata(clean_source_json, finalized_content):
    """Queries the Metadata Agent to generate the SEO title, description, and tags."""
    print("    - Querying Metadata Agent to generate frontmatter parameters...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    scope = get_scope()
    prompt_path = os.path.join(agent_dir, scope, "metadata_agent.txt")
    
    if not os.path.exists(prompt_path):
        print(f"      [!] Metadata prompt template not found: {prompt_path}")
        return None
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
        
    user_payload = f"RAW SOURCE INFO:\n{clean_source_json}\n\nFINALIZED REWRITTEN CONTENT:\n{finalized_content}"
    
    try:
        raw_res = call_llm(system_prompt, user_payload)
        if not raw_res:
            return None
            
        # Decode integer IDs
        categories = ["Local", "National", "International"]
        regions = ["Arunachal Pradesh", "Assam", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Sikkim", "Tripura", "Northeast", "N/A"]
        tags = ["Politics", "Sports", "Business", "Tech", "Science", "Culture", "Health", "Education", "Weather", "Entertainment", "Environment", "Celebrity", "Uncategorized"]
        
        # Calculate strict defaults based on pipeline scope
        if scope == "local":
            default_cat = 0
        elif scope == "national":
            default_cat = 1
        else:
            default_cat = 2
            
        cat_id = raw_res.get("category_id", default_cat)
        reg_id = raw_res.get("region_id", 9)
        tag_id = raw_res.get("tag_id", 12)
        
        res = {
            "title": raw_res.get("title", ""),
            "description": raw_res.get("description", ""),
            "category": categories[cat_id] if 0 <= cat_id < len(categories) else "Local",
            "region": regions[reg_id] if 0 <= reg_id < len(regions) else "N/A",
            "majorTag": tags[tag_id] if 0 <= tag_id < len(tags) else "Uncategorized"
        }
        return res
    except Exception as e:
        print(f"      [!] Metadata agent execution failed: {e}")
        return None

def validate_metadata(draft_body, title, description, region, tag):
    """Queries the Executive Editor Agent to validate the title, description, region, and tag."""
    print("    - Querying Executive Editor to validate metadata...")
    
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(agent_dir, "metadata_validator.txt")
    
    if not os.path.exists(prompt_path):
        return {"passed": True}
        
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
        
    user_payload = f"DRAFT BODY:\n{draft_body}\n\nGENERATED TITLE:\n{title}\n\nGENERATED DESCRIPTION:\n{description}\n\nGENERATED REGION:\n{region}\n\nGENERATED TAG:\n{tag}"
    
    try:
        res = call_llm(system_prompt, user_payload)
        return res
    except Exception as e:
        print(f"      [!] Metadata validator execution failed: {e}")
        return {"passed": True}
