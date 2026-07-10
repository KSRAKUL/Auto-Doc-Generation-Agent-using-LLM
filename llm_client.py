"""
LLM Client for AutoDoc Agent.
Thin, swappable wrapper around LLM providers (Ollama / Groq / Gemini).
"""

import json
import time
import logging
import httpx

import config

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified interface for calling different LLM providers."""

    def __init__(self):
        self.provider = config.LLM_PROVIDER.lower()
        self.max_retries = config.MAX_RETRIES
        self.timeout = config.REQUEST_TIMEOUT
        logger.info(f"LLM Client initialized — provider: {self.provider}")

    # ── Public API ──────────────────────────────────────────────────────────

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a prompt to the configured LLM and return the text response.
        Retries on transient failures with exponential backoff.
        """
        last_error = None

        for attempt in range(1, self.max_retries + 2):  # +2 because range is exclusive & attempt 1 is first try
            try:
                logger.info(f"LLM call attempt {attempt}/{self.max_retries + 1}")

                if self.provider == "ollama":
                    return self._call_ollama(system_prompt, user_prompt)
                elif self.provider == "groq":
                    return self._call_groq(system_prompt, user_prompt)
                elif self.provider == "gemini":
                    return self._call_gemini(system_prompt, user_prompt)
                else:
                    raise ValueError(f"Unsupported LLM provider: {self.provider}")

            except Exception as e:
                last_error = e
                logger.warning(f"LLM call attempt {attempt} failed: {e}")
                if attempt <= self.max_retries:
                    wait = 2 ** attempt  # exponential backoff: 2s, 4s
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)

        raise RuntimeError(
            f"LLM call failed after {self.max_retries + 1} attempts. "
            f"Last error: {last_error}"
        )

    # ── Ollama ──────────────────────────────────────────────────────────────

    def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        """Call Ollama's local API."""
        url = f"{config.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": config.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": config.TEMPERATURE,
                "num_predict": config.MAX_TOKENS,
            },
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    # ── Groq ────────────────────────────────────────────────────────────────

    def _call_groq(self, system_prompt: str, user_prompt: str) -> str:
        """Call Groq's cloud API."""
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in environment.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.TEMPERATURE,
            "max_tokens": config.MAX_TOKENS,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    # ── Gemini ──────────────────────────────────────────────────────────────

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Call Google Gemini's REST API."""
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in environment.")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{config.GEMINI_MODEL}:generateContent"
            f"?key={config.GEMINI_API_KEY}"
        )
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "temperature": config.TEMPERATURE,
                "maxOutputTokens": config.MAX_TOKENS,
            },
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


# ── Singleton instance ──────────────────────────────────────────────────────

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
