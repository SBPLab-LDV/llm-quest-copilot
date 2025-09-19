"""HTTP client for interacting with an Ollama server."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests


logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Raised when the Ollama server reports an error."""


class OllamaClient:
    """Lightweight wrapper for Ollama's REST API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "gpt-oss:20b",
        timeout: int = 120,
        default_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.default_options = default_options or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_response(self, prompt: str, **options) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {**self.default_options, **options},
        }

        url = f"{self.base_url}/api/generate"
        logger.debug("POST %s payload keys=%s", url, list(payload.keys()))
        resp = requests.post(url, json=payload, timeout=self.timeout)

        if resp.status_code != 200:
            raise OllamaError(f"HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        if not isinstance(data, dict):
            raise OllamaError("Unexpected Ollama response format")

        if data.get("error"):
            raise OllamaError(str(data["error"]))

        # Non-stream responses include the entire text under "response".
        response_text = data.get("response", "")
        if not isinstance(response_text, str):
            response_text = str(response_text)

        return response_text

