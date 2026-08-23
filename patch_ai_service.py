import re

with open('ai_service.py', 'r') as f:
    code = f.read()

# Add helper functions for provider check
helpers = '''
def _get_groq_key():
    return os.environ.get('GROQ_API_KEY', GROQ_API_KEY).strip()

def _get_ollama_url():
    return os.environ.get('OLLAMA_BASE_URL', OLLAMA_BASE_URL).strip()

def _is_ollama_available():
    url = _get_ollama_url()
    try:
        resp = requests.get(f"{url}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False
'''

if '_get_groq_key()' not in code:
    code = code.replace("RATE_LIMIT_SECONDS = 3  # Reduced to 3 seconds for better UX\n", "RATE_LIMIT_SECONDS = 3  # Reduced to 3 seconds for better UX\n" + helpers)

with open('ai_service.py', 'w') as f:
    f.write(code)

print("Updated ai_service.py with helper functions")
