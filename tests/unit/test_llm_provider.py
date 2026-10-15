import io
import json
import pytest
from urllib.error import HTTPError
from backend.app import llm_provider as provider


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('LLM_MODEL', 'gemini-flash-latest')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret')


def test_disabled_and_missing_key_status(monkeypatch):
    monkeypatch.delenv('LLM_PROVIDER', raising=False)
    assert not provider.assistant_status()['enabled']
    monkeypatch.setenv('LLM_PROVIDER', 'gemini')
    monkeypatch.setenv('LLM_MODEL', 'gemini-flash-latest')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    assert not provider.assistant_status()['enabled']


def test_gemini_structured_request_keeps_secret_out_of_payload(configured, monkeypatch):
    def request(req, timeout):
        assert req.full_url.endswith('/gemini-flash-latest:generateContent')
        assert 'test-secret' not in req.full_url
        body = json.loads(req.data)
        assert 'test-secret' not in req.data.decode()
        assert body['generationConfig']['responseJsonSchema'] == {'type': 'object'}
        assert req.get_header('X-goog-api-key') == 'test-secret'
        assert timeout <= 120
        return io.BytesIO(json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"ok":true}'}]}}]}).encode())
    monkeypatch.setattr(provider, 'urlopen', request)
    assert provider.generate_structured('system', {'question': 'battery'}, {'type': 'object'}) == {'ok': True}


@pytest.mark.parametrize('payload', [
    {}, {'candidates': []},
    {'candidates': [{'finishReason': 'MAX_TOKENS'}]},
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'not json'}]}}]},
])
def test_invalid_provider_outputs_fail_cleanly(configured, monkeypatch, payload):
    monkeypatch.setattr(provider, 'urlopen', lambda *_a, **_k: io.BytesIO(json.dumps(payload).encode()))
    with pytest.raises(provider.AssistanceUnavailable, match='invalid structured'):
        provider.generate_structured('s', {}, {})


def test_errors_do_not_echo_provider_body_or_key(configured, monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError('https://provider', 403, 'test-secret', {}, io.BytesIO(b'test-secret'))
    monkeypatch.setattr(provider, 'urlopen', fail)
    with pytest.raises(provider.AssistanceUnavailable) as error:
        provider.generate_structured('s', {}, {})
    assert 'test-secret' not in str(error.value)


def test_ollama_is_local_and_finite_timeout_required(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('LLM_MODEL', 'mistral:latest')
    monkeypatch.setenv('OLLAMA_BASE_URL', 'https://external.example')
    with pytest.raises(provider.AssistanceUnavailable, match='local HTTP'):
        provider.generate_structured('s', {}, {})
    monkeypatch.setenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    monkeypatch.setenv('LLM_TIMEOUT_SECONDS', 'nan')
    with pytest.raises(provider.AssistanceUnavailable, match='between'):
        provider.generate_structured('s', {}, {})


def test_busy_request_is_rejected_without_network(configured):
    provider._generation_slot.acquire()
    try:
        with pytest.raises(provider.AssistanceBusy):
            provider.generate_structured('s', {}, {})
    finally:
        provider._generation_slot.release()


def test_groq_missing_credentials_disables_assistant(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'groq')
    monkeypatch.setenv('LLM_MODEL', 'openai/gpt-oss-20b')
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    assert not provider.assistant_status()['enabled']
    assert 'GROQ_API_KEY' in provider.assistant_status()['reason']


def test_groq_schema_auth_and_response(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'groq')
    monkeypatch.setenv('LLM_MODEL', 'openai/gpt-oss-20b')
    monkeypatch.setenv('GROQ_API_KEY', 'test-groq-secret')
    def request(req, **kwargs):
        assert req.full_url == 'https://api.groq.com/openai/v1/chat/completions'
        assert req.get_header('Authorization') == 'Bearer test-groq-secret'
        body = json.loads(req.data)
        assert body['response_format']['json_schema']['strict']
        assert body['model'] == 'openai/gpt-oss-20b'
        assert b'test-groq-secret' not in req.data
        return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]}).encode())
    monkeypatch.setattr(provider, 'urlopen', request)
    assert provider.generate_structured('system', {}, {'type': 'object'}) == {'ok': True}
