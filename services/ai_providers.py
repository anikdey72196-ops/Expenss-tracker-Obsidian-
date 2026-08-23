import os
import requests
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq Configuration
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip()

# llama-3.1-8b-instant was deprecated by Groq — use llama3-8b-8192 as the
# fast default. We keep a fallback list so if one model is retired the code
# automatically retries with the next available one.
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama3-8b-8192')
GROQ_FALLBACK_MODELS = [
    'llama3-8b-8192',
    'llama3-70b-8192',
    'mixtral-8x7b-32768',
    'gemma2-9b-it',
]

# ---------------------------------------------------------------------------
# Ollama (local) Configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'gemma4:26b')


def get_active_ollama_model():
    """Return the best available Ollama model. Falls back gracefully."""
    preferred = os.environ.get('OLLAMA_MODEL', OLLAMA_MODEL)
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        resp.raise_for_status()
        installed = [m.get('name', '') for m in resp.json().get('models', [])]
        if preferred in installed:
            return preferred
        # Prefer known fast chat models
        for candidate in installed:
            cl = candidate.lower()
            if any(k in cl for k in ['qwen', 'coder', 'gemma', 'llama', 'mistral']):
                logger.info("Ollama: preferred model %s not found, using %s", preferred, candidate)
                return candidate
        if installed:
            return installed[0]
    except requests.exceptions.RequestException as exc:
        logger.warning("Cannot reach Ollama at %s: %s", OLLAMA_BASE_URL, exc)
    return preferred


def call_groq(messages, stream=False, max_tokens=512, timeout=30):
    """Call Groq Cloud AI API. Tries GROQ_MODEL first, then fallback models."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    # Build ordered list of models to try (primary first, then fallbacks)
    current_primary = os.environ.get('GROQ_MODEL', GROQ_MODEL)
    models_to_try = [current_primary] + [m for m in GROQ_FALLBACK_MODELS if m != current_primary]

    last_error = None
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.5,
            "max_tokens": max_tokens,
        }
        try:
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
        except requests.exceptions.HTTPError as exc:
            # 404 = model_not_found → try next fallback
            if exc.response is not None and exc.response.status_code == 404:
                logger.warning("Groq model '%s' not found, trying next fallback.", model)
                last_error = exc
                if stream:
                    continue  # fallback only works for non-stream since stream returned early
            else:
                raise
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.error("Groq API request error with model '%s': %s", model, exc)
            raise

    # All models exhausted
    raise RuntimeError(f"All Groq models failed. Last error: {last_error}")


def call_ollama(messages, stream=False, num_predict=512, timeout=15):
    """Call Ollama local API with auto-resolved model."""
    url = f"{OLLAMA_BASE_URL}/api/chat"
    model_name = get_active_ollama_model()
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": 0.5,
            "num_predict": num_predict,
        },
    }

    if stream:
        resp = requests.post(url, json=payload, stream=True, timeout=timeout)
        resp.raise_for_status()
        return resp
    else:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get('message', {}).get('content', '')


def call_llm_single(messages, max_tokens=256, timeout=15):
    """Call active LLM: Groq Cloud first, then local Ollama as fallback."""
    current_groq_key = os.environ.get('GROQ_API_KEY', GROQ_API_KEY).strip()
    if current_groq_key:
        try:
            return call_groq(messages, stream=False, max_tokens=max_tokens, timeout=timeout)
        except Exception as exc:
            logger.warning("Groq failed, falling back to Ollama: %s", exc)
    return call_ollama(messages, stream=False, num_predict=max_tokens, timeout=timeout)


