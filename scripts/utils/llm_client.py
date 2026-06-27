import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

API_KEYS = []
for i in range(1, 10):
    key = os.environ.get(f"LLM_API_KEY_{i}")
    if key:
        API_KEYS.append(key)

# Fallback to single key if numbered keys aren't used
if not API_KEYS and os.environ.get("LLM_API_KEY"):
    API_KEYS.append(os.environ.get("LLM_API_KEY"))

if not API_KEYS:
    raise ValueError("No LLM_API_KEY_X environment variables found.")

API_URL = os.environ.get("LLM_API_URL", "https://integrate.api.nvidia.com/v1")
MODEL_NAME = os.environ.get("LLM_MODEL", "meta/llama-3.1-70b-instruct")

def get_client(key_index=0):
    """Returns an OpenAI client for the given key index."""
    if key_index >= len(API_KEYS):
        raise ValueError(f"API key index {key_index} out of range (only {len(API_KEYS)} keys available)")
    return OpenAI(base_url=API_URL, api_key=API_KEYS[key_index])

def clean_json_string(text):
    """Strips markdown code blocks (e.g., ```json ... ```) from LLM responses before parsing."""
    if not text:
        return ""
    text = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

def call_llm(system_prompt, user_content, temperature=0.3, max_tokens=2048, timeout=90):
    """
    Unified LLM call function with robust choice execution, fallback stripping,
    and structured JSON loads. It will attempt to rotate through available API keys
    if it encounters a 429 Too Many Requests error.
    """
    last_exception = None
    for key_index in range(len(API_KEYS)):
        try:
            client = get_client(key_index)
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            raw_content = completion.choices[0].message.content
            cleaned_content = clean_json_string(raw_content)
            return json.loads(cleaned_content)
        except Exception as e:
            last_exception = e
            # If it's a 429 Rate Limit error, continue to the next key. Otherwise raise immediately.
            if hasattr(e, 'status_code') and e.status_code == 429:
                print(f"[!] Hit 429 Rate Limit on API Key {key_index+1}. Falling back to next key...")
                continue
            elif '429' in str(e):
                print(f"[!] Hit 429 Rate Limit on API Key {key_index+1}. Falling back to next key...")
                continue
            else:
                raise e
    
    # If we exhausted all keys
    raise Exception(f"All {len(API_KEYS)} API keys returned 429 errors. Last error: {last_exception}")
