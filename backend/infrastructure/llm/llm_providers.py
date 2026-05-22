"""
LLM provider abstraction with timeout protection for Gmail Genie.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Dict, Optional

import ollama
import threading

# Optional host override for Docker / remote Ollama
_ollama_host = os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_BASE_URL")
if _ollama_host:
    _host = _ollama_host.replace("http://", "").replace("https://", "").rstrip("/")
    if _host:
        os.environ.setdefault("OLLAMA_HOST", _host)

OLLAMA_SEMAPHORE = threading.Semaphore(2)


class BaseLLMProvider(ABC):
    """Abstract chat completion provider."""

    def __init__(self, timeout_seconds: float = 90.0) -> None:
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def _chat_impl(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        pass

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
    ) -> str:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self._chat_impl,
                system_prompt,
                user_prompt,
                temperature,
            )
            try:
                return future.result(timeout=self.timeout_seconds)
            except FuturesTimeoutError as exc:
                raise TimeoutError(
                    f"{self.provider_name} inference timed out after "
                    f"{self.timeout_seconds}s"
                ) from exc

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass


class OllamaProvider(BaseLLMProvider):
    """Local Ollama — fast/deep semantic paths."""

    def __init__(self, model: str, timeout_seconds: float = 90.0) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self.model = model

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _chat_impl(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": temperature},
        )
        return response["message"]["content"].strip()


class GroqProvider(BaseLLMProvider):
    """Groq cloud — rare escalation only."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self.model = model
        self.api_key = (api_key or os.environ.get("GROQ_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY missing in .env — see .env.example"
            )
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from groq import Groq
            except ImportError as exc:
                raise ImportError("pip install groq") from exc
            self._client = Groq(api_key=self.api_key)
        return self._client

    @property
    def provider_name(self) -> str:
        return "groq"

    def _chat_impl(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()


def create_primary_provider(llm_config: Dict[str, Any]) -> BaseLLMProvider:
    timeout = float(llm_config.get("inference_timeout_seconds", 90))
    model = llm_config.get("model", "mistral:7b-instruct")  # local default
    return OllamaProvider(model=model, timeout_seconds=timeout)


def create_groq_escalation_provider(
    llm_config: Dict[str, Any],
) -> Optional[GroqProvider]:
    if not llm_config.get("escalation_enabled", True):
        return None
    api_key = (
        llm_config.get("groq_api_key")
        or os.environ.get("GROQ_API_KEY", "")
    ).strip()
    if not api_key:
        return None
    model = llm_config.get(
        "escalation_model",
        os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )
    timeout = float(llm_config.get("groq_timeout_seconds", 60))
    return GroqProvider(model=model, api_key=api_key, timeout_seconds=timeout)


def create_llm_provider(llm_config: Dict[str, Any]) -> BaseLLMProvider:
    return create_primary_provider(llm_config)
