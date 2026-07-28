"""
Multi-provider LLM client for Content Skeleton Ripper.
Uses OpenAI-compatible /chat/completions format for all providers.
Endpoints, API keys, and models are configurable via env vars.
"""

import os
import json
import time
import traceback
import requests
from dataclasses import dataclass
from typing import Optional
from agent_core.recon.utils.logger import get_logger

logger = get_logger()


@dataclass
class ModelInfo:
    id: str
    name: str
    cost_tier: str


def _env_or_default(key: str, default: str) -> str:
    return os.getenv(key, default)


LLM_BASE_URL = _env_or_default("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
LLM_MODEL = _env_or_default("LLM_MODEL", "gpt-4o-mini")
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1", "yes")

TRANSCRIBE_BASE_URL = _env_or_default("TRANSCRIBE_BASE_URL", "https://api.openai.com/v1")
TRANSCRIBE_API_KEY = os.getenv("TRANSCRIBE_API_KEY") or os.getenv("OPENAI_API_KEY")
TRANSCRIBE_MODEL = _env_or_default("TRANSCRIBE_MODEL", "whisper-1")
TRANSCRIBE_PROVIDER = _env_or_default("TRANSCRIBE_PROVIDER", "openai")
WHISPER_MODEL = _env_or_default("WHISPER_MODEL", "small.en")


@dataclass
class ProviderConfig:
    id: str
    name: str
    api_key_env: str
    base_url: str
    models: list[ModelInfo]


PROVIDERS = {
    'openai': ProviderConfig(
        id='openai', name='OpenAI', api_key_env='LLM_API_KEY',
        base_url=LLM_BASE_URL,
        models=[
            ModelInfo('gpt-4o-mini', 'GPT-4o Mini (Recommended)', 'low'),
            ModelInfo('gpt-4o', 'GPT-4o', 'medium'),
        ]
    ),
    'custom': ProviderConfig(
        id='custom', name='Custom Endpoint', api_key_env='LLM_API_KEY',
        base_url=LLM_BASE_URL,
        models=[
            ModelInfo(LLM_MODEL, f'{LLM_MODEL} (from LLM_MODEL env)', 'custom'),
        ]
    ),
    'local': ProviderConfig(
        id='local', name='Local (Ollama)', api_key_env='',
        base_url=_env_or_default('OLLAMA_BASE_URL', 'http://localhost:11434'),
        models=[
            ModelInfo('qwen3', 'Qwen 3 (Recommended)', 'free'),
            ModelInfo('llama3', 'Llama 3', 'free'),
            ModelInfo('mistral', 'Mistral', 'free'),
        ]
    ),
}


class LLMClient:
    DEFAULT_MAX_RETRIES = 3
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(self, provider: str = None, model: str = None, timeout: int = 120, max_retries: int = 3):
        if provider is None:
            provider = 'custom'
        if model is None:
            model = LLM_MODEL

        if provider not in PROVIDERS:
            if provider in ('anthropic', 'google'):
                logger.warning("LLM", f"Provider '{provider}' no longer supported directly. "
                                   f"Use 'custom' with LLM_BASE_URL pointing to an OpenAI-compatible endpoint.")
                provider = 'custom'
            else:
                raise ValueError(f"Unknown provider: {provider}. Valid: {list(PROVIDERS.keys())}")

        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.config = PROVIDERS[provider]

        self.api_key = None
        if self.config.api_key_env:
            self.api_key = os.getenv(self.config.api_key_env) or os.getenv('OPENAI_API_KEY')
            if not self.api_key and provider != 'local':
                logger.warning("LLM", f"No API key set via {self.config.api_key_env} or OPENAI_API_KEY")

        logger.info("LLM", f"Client initialized: {provider}/{model} at {self.config.base_url}")

    def complete(self, prompt: str, temperature: float = 0.7) -> str:
        return self.chat(system_prompt=None, user_prompt=prompt, temperature=temperature)

    def chat(self, user_prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                if self.provider == 'local':
                    return self._call_ollama(system_prompt, user_prompt, temperature)
                return self._call_openai_compatible(system_prompt, user_prompt, temperature)
            except requests.exceptions.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response is not None else 0
                if status_code in self.RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    delay = min(1.0 * (2 ** attempt), 30.0)
                    logger.warning("LLM", f"HTTP {status_code}, retrying in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(1.0 * (2 ** attempt), 30.0)
                    logger.warning("LLM", f"Connection error, retrying in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                raise
            except Exception:
                raise

        raise last_exception or Exception("Max retries exceeded")

    def _call_openai_compatible(self, system_prompt, user_prompt, temperature):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        base = self.config.base_url.rstrip('/')
        response = requests.post(
            f"{base}/chat/completions",
            headers=headers,
            json={"model": self.model, "messages": messages, "temperature": temperature},
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get('choices', [])
        if choices:
            return choices[0]['message']['content']
        raise ValueError(f"Unexpected API response: no choices. Keys: {list(data.keys())}")

    def _call_ollama(self, system_prompt, user_prompt, temperature):
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}" if system_prompt else user_prompt
        base = self.config.base_url.rstrip('/')
        response = requests.post(
            f"{base}/api/generate",
            json={"model": self.model, "prompt": full_prompt, "stream": False, "options": {"temperature": temperature}},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()['response']


def get_available_providers() -> list[dict]:
    result = []
    for provider_id, config in PROVIDERS.items():
        available = False
        models = []
        if provider_id == 'local':
            try:
                base = config.base_url.rstrip('/')
                response = requests.get(f'{base}/api/tags', timeout=2)
                if response.status_code == 200:
                    available = True
                    data = response.json()
                    installed = {m['name'].split(':')[0] for m in data.get('models', [])}
                    models = [{'id': m.id, 'name': m.name, 'cost_tier': m.cost_tier}
                              for m in config.models if m.id in installed]
            except requests.exceptions.RequestException:
                pass
        else:
            api_key = os.getenv(config.api_key_env) or os.getenv('OPENAI_API_KEY')
            if api_key or not config.api_key_env:
                available = True
                models = [{'id': m.id, 'name': m.name, 'cost_tier': m.cost_tier} for m in config.models]
        result.append({'id': config.id, 'name': config.name, 'available': available, 'models': models})
    return result