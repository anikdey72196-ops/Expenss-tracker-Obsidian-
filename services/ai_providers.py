import os
import requests
import json

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip()
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.1-8b-instant')

OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'gemma4:26b')


def get_active_ollama_model():
    """Determine active Ollama model, falling back to installed models if needed."""
    model = os.environ.get('OLLAMA_MODEL', OLLAMA_MODEL)
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get('name', '') for m in resp.json().get('models', [])]
            if model in models:
                return model
            for m in models:
                if any(k in m.lower() for k in ['qwen', 'coder', 'gemma', 'llama', 'mistral']):
                    return m
            if models:
                return models[0]
    except Exception:
        pass
    return model


def call_groq(messages, stream=False, max_tokens=256, timeout=30):
    """Call Groq Cloud AI API."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "stream": stream,
        "temperature": 0.5,
        "max_tokens": max_tokens
    }

    if stream:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
        resp.raise_for_status()
        return resp
    else:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get('choices', [])
        if choices:
            return choices[0].get('message', {}).get('content', '')
        return ''


def call_ollama(messages, stream=False, num_predict=256, timeout=5):
    """Call Ollama chat API with auto-resolved model and timeout handling."""
    url = f"{OLLAMA_BASE_URL}/api/chat"
    model_name = get_active_ollama_model()
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": 0.5,
            "num_predict": num_predict,
        }
    }

    if stream:
        resp = requests.post(url, json=payload, stream=True, timeout=timeout)
        resp.raise_for_status()
        return resp
    else:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get('message', {}).get('content', '')


def call_llm_single(messages, max_tokens=256, timeout=15):
    """Call active LLM (Groq first, fallback to Ollama)."""
    current_groq_key = os.environ.get('GROQ_API_KEY', GROQ_API_KEY).strip()
    if current_groq_key:
        try:
            return call_groq(messages, stream=False, max_tokens=max_tokens, timeout=timeout)
        except Exception as e:
            print(f"Groq API Error, trying Ollama fallback: {e}")
    return call_ollama(messages, stream=False, num_predict=max_tokens, timeout=timeout)
