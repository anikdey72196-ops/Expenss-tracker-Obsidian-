with open('ai_service.py', 'r') as f:
    content = f.read()

# Update _call_groq to use _get_groq_key()
content = content.replace(
    'headers = {\n        "Authorization": f"Bearer {GROQ_API_KEY}",',
    'headers = {\n        "Authorization": f"Bearer {_get_groq_key()}",'
)

# Update _call_ollama to use _get_ollama_url()
content = content.replace(
    'url = f"{OLLAMA_BASE_URL}/api/chat"',
    'url = f"{_get_ollama_url()}/api/chat"'
)

# Update _get_active_ollama_model
content = content.replace(
    'resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)',
    'resp = requests.get(f"{_get_ollama_url()}/api/tags", timeout=2)'
)

# Update _call_llm_single
new_llm_single = '''def _call_llm_single(messages, max_tokens=256, timeout=15):
    """Call active LLM (Groq first, fallback to Ollama if available)."""
    groq_key = _get_groq_key()
    if groq_key:
        try:
            return _call_groq(messages, stream=False, max_tokens=max_tokens, timeout=timeout)
        except Exception as e:
            print(f"Groq API Error: {e}")
    if _is_ollama_available():
        return _call_ollama(messages, stream=False, num_predict=max_tokens, timeout=timeout)
    return ""'''

import re
content = re.sub(
    r'def _call_llm_single\(.*?\):.*?(?=\n\ndef|\n@|\Z)',
    new_llm_single,
    content,
    flags=re.DOTALL
)

with open('ai_service.py', 'w') as f:
    f.write(content)

print("Updated LLM calls in ai_service.py")
