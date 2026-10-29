"""Opt-in structured generation; never downloads or replaces ML models."""
import json
import math
import os
import re
from threading import BoundedSemaphore
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class AssistanceUnavailable(RuntimeError):
    pass


class AssistanceBusy(AssistanceUnavailable):
    pass


_generation_slot = BoundedSemaphore(1)


def inline_schema(schema):
    """Gonka rejects $defs/$ref; inline our bounded, nonrecursive schemas."""
    definitions = schema.get('$defs', {})

    def expand(value, active=()):
        if isinstance(value, list):
            return [expand(item, active) for item in value]
        if not isinstance(value, dict):
            return value
        value = dict(value)
        ref = value.pop('$ref', None)
        if ref is not None:
            if not ref.startswith('#/$defs/') or ref in active:
                raise ValueError('Unsupported schema reference')
            name = ref[len('#/$defs/'):]
            if name not in definitions:
                raise ValueError('Unknown schema reference')
            value = {**expand(definitions[name], (*active, ref)), **value}
        return {key: expand(item, active) for key, item in value.items() if key != '$defs'}

    return expand(schema)


def assistant_status():
    provider = os.environ.get('LLM_PROVIDER', 'disabled').strip().lower()
    model = os.environ.get('LLM_MODEL', '').strip()
    if provider == 'disabled':
        return {'enabled': False, 'provider': None, 'model': None,
            'reason': 'Optional assistant is disabled. Configure LLM_PROVIDER and LLM_MODEL on the server.'}
    if provider not in {'ollama', 'gemini', 'groq', 'gonka'} or not model:
        return {'enabled': False, 'provider': provider, 'model': model or None,
            'reason': 'Set LLM_PROVIDER to gonka, groq, gemini or ollama, and configure LLM_MODEL.'}
    if provider == 'gonka' and not os.environ.get('GONKA_API_KEY', '').strip():
        return {'enabled': False, 'provider': provider, 'model': model, 'reason': 'Set GONKA_API_KEY on the server to enable Gonka Broker.'}
    if provider == 'gemini' and not os.environ.get('GEMINI_API_KEY', '').strip():
        return {'enabled': False, 'provider': provider, 'model': model, 'reason': 'Set GEMINI_API_KEY on the server to enable Gemini.'}
    if provider == 'groq' and not os.environ.get('GROQ_API_KEY', '').strip():
        return {'enabled': False, 'provider': provider, 'model': model, 'reason': 'Set GROQ_API_KEY on the server to enable Groq.'}
    return {'enabled': True, 'provider': provider, 'model': model,
        'reason': 'Provider configured. Availability is checked when you request assistance.'}


def generate_structured(system, payload, schema):
    status = assistant_status()
    if not status['enabled']:
        raise AssistanceUnavailable(status['reason'])
    base_url = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlparse(base_url)
    if status['provider'] == 'ollama' and (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1', 'host.docker.internal'} or parsed.username or parsed.password):
        raise AssistanceUnavailable('Ollama must use a local HTTP address.')
    try:
        timeout = float(os.environ.get('LLM_TIMEOUT_SECONDS', '90'))
        if not math.isfinite(timeout) or not 1 <= timeout <= 120:
            raise ValueError
    except ValueError as exc:
        raise AssistanceUnavailable('LLM_TIMEOUT_SECONDS must be between 1 and 120.') from exc
    if not _generation_slot.acquire(blocking=False):
        raise AssistanceBusy('The assistant is busy. Try again after this request finishes.')
    try:
        body = json.dumps({'model': status['model'], 'stream': False, 'format': schema,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(payload)}],
            'options': {'temperature': 0, 'num_predict': 1200, 'num_ctx': 8192}}).encode()
        headers = {'Content-Type': 'application/json', 'User-Agent': 'ReviewTagGenerator/0.1'}
        endpoint = base_url + '/api/chat'
        if status['provider'] == 'gemini':
            if not re.fullmatch(r'[a-zA-Z0-9_.-]+', status['model']):
                raise AssistanceUnavailable('Invalid Gemini model identifier.')
            endpoint = 'https://generativelanguage.googleapis.com/v1beta/models/' + status['model'] + ':generateContent'
            headers['X-goog-api-key'] = os.environ['GEMINI_API_KEY'].strip()
            body = json.dumps({'systemInstruction': {'parts': [{'text': system}]},
                'contents': [{'role': 'user', 'parts': [{'text': json.dumps(payload)}]}],
                'generationConfig': {'responseMimeType': 'application/json', 'responseJsonSchema': schema,
                    'maxOutputTokens': 4096, 'temperature': 0}}).encode()
        elif status['provider'] in {'groq', 'gonka'}:
            gonka = status['provider'] == 'gonka'
            endpoint = 'https://proxy.gonkabroker.com/v1/chat/completions' if gonka else 'https://api.groq.com/openai/v1/chat/completions'
            headers['Authorization'] = 'Bearer ' + os.environ['GONKA_API_KEY' if gonka else 'GROQ_API_KEY'].strip()
            # Include the contract in the prompt as well as requesting constrained JSON.
            # Gonka's available models can differ in response_format enforcement.
            instruction = system + ('\nReturn only a JSON object matching this JSON Schema:\n' + json.dumps(schema) if gonka else '')
            request_body = {'model': status['model'], 'stream': False,
                'messages': [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': json.dumps(payload)}],
                'temperature': 0,
                'response_format': {'type': 'json_schema', 'json_schema': {
                    'name': 'review_assistance', 'strict': True, 'schema': inline_schema(schema) if gonka else schema}}}
            request_body['max_tokens' if gonka else 'max_completion_tokens'] = 4096
            if gonka and status['model'] != 'MiniMaxAI/MiniMax-M2.7':
                request_body['reasoning_effort'] = 'none'
            body = json.dumps(request_body).encode()
        request = Request(endpoint, data=body, headers=headers)
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Response too large')
        response = json.loads(raw)
        if status['provider'] == 'gemini':
            candidate = response['candidates'][0]
            if candidate.get('finishReason') != 'STOP':
                raise ValueError('Incomplete response')
            content = ''.join(part.get('text', '') for part in candidate['content']['parts'] if not part.get('thought'))
        elif status['provider'] in {'groq', 'gonka'}:
            choice = response['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('Incomplete response')
            content = choice['message']['content']
        else:
            if response.get('done') is not True or response.get('done_reason') == 'length':
                raise ValueError('Incomplete response')
            content = response['message']['content']
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError('Expected structured object')
        return result
    except HTTPError as exc:
        if exc.code in (500, 502, 503, 504):
            message = 'The assistant provider is temporarily unavailable or experiencing high demand. Try again shortly.'
        elif exc.code == 429:
            message = 'The assistant provider rate or quota limit was reached. Check your quota or try again later.'
        else:
            message = 'The assistant provider rejected the request. Check the configured credentials and model.'
        raise AssistanceUnavailable(message) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AssistanceUnavailable('Assistant unavailable. Check the configured provider and connection.') from exc
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        raise AssistanceUnavailable('The assistant returned an incomplete or invalid structured response. Try again.') from exc
    finally:
        _generation_slot.release()
