with open('ai_service.py', 'r') as f:
    code = f.read()

old_generate = '''        def generate():
            try:
                if current_groq_key:
                    # Groq Cloud API Streaming
                    resp = _call_groq(messages, stream=True, max_tokens=300, timeout=30)
                    for line in resp.iter_lines():
                        if line:
                            decoded = line.decode('utf-8')
                            if decoded.startswith('data: '):
                                raw_data = decoded[6:].strip()
                                if raw_data == '[DONE]':
                                    yield f"data: {json.dumps({'done': True})}\\n\\n"
                                    break
                                try:
                                    chunk = json.loads(raw_data)
                                    delta = chunk.get('choices', [{}])[0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        yield f"data: {json.dumps({'content': content})}\\n\\n"
                                except Exception:
                                    pass
                else:
                    # Local Ollama Streaming Fallback
                    resp = _call_ollama(messages, stream=True, num_predict=256, timeout=300)
                    for line in resp.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            msg = chunk.get('message', {})
                            content = msg.get('content', '')
                            if content:
                                yield f"data: {json.dumps({'content': content})}\\n\\n"
                            if chunk.get('done', False):
                                yield f"data: {json.dumps({'done': True})}\\n\\n"
                                break

            except requests.exceptions.Timeout:
                yield f"data: {json.dumps({'error': 'The AI model took too long to respond (timeout). Please try sending your message again!'})}\\n\\n"
            except requests.exceptions.ConnectionError:
                yield f"data: {json.dumps({'error': 'Cannot connect to AI service. Please check your GROQ_API_KEY or local Ollama status.'})}\\n\\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'AI generation error: {str(e)}'})}\\n\\n"'''

new_generate = '''        def generate():
            try:
                groq_key = _get_groq_key()
                if groq_key:
                    # Groq Cloud API Streaming
                    resp = _call_groq(messages, stream=True, max_tokens=300, timeout=30)
                    for line in resp.iter_lines():
                        if line:
                            decoded = line.decode('utf-8')
                            if decoded.startswith('data: '):
                                raw_data = decoded[6:].strip()
                                if raw_data == '[DONE]':
                                    yield f"data: {json.dumps({'done': True})}\\n\\n"
                                    break
                                try:
                                    chunk = json.loads(raw_data)
                                    delta = chunk.get('choices', [{}])[0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        yield f"data: {json.dumps({'content': content})}\\n\\n"
                                except Exception:
                                    pass
                elif _is_ollama_available():
                    # Local Ollama Streaming Fallback
                    resp = _call_ollama(messages, stream=True, num_predict=256, timeout=120)
                    for line in resp.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            msg = chunk.get('message', {})
                            content = msg.get('content', '')
                            if content:
                                yield f"data: {json.dumps({'content': content})}\\n\\n"
                            if chunk.get('done', False):
                                yield f"data: {json.dumps({'done': True})}\\n\\n"
                                break
                else:
                    yield f"data: {json.dumps({'error': 'No AI service configured. Set GROQ_API_KEY environment variable or start local Ollama.'})}\\n\\n"

            except requests.exceptions.Timeout:
                yield f"data: {json.dumps({'error': 'The AI model took too long to respond (timeout). Please try sending your message again!'})}\\n\\n"
            except requests.exceptions.ConnectionError:
                yield f"data: {json.dumps({'error': 'Cannot connect to AI service. Please check your GROQ_API_KEY or local Ollama status.'})}\\n\\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'AI generation error: {str(e)}'})}\\n\\n"'''

if old_generate in code:
    code = code.replace(old_generate, new_generate)
    with open('ai_service.py', 'w') as f:
        f.write(code)
    print("Patched generate generator in ai_service.py")
else:
    print("old_generate block not found")
