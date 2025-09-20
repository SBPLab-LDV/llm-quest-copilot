"""HTTP client for interacting with an Ollama server."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

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

        raw_text = resp.text if hasattr(resp, "text") else ""
        logger.debug("Ollama raw response length: %s", len(raw_text))
        logger.debug("Ollama raw response (first 500 chars): %s", raw_text[:500])

        try:
            snapshot_dir = Path("logs") / "debug" / "ollama_raw"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            snapshot_file = snapshot_dir / f"{snapshot_name}_{uuid.uuid4().hex}.json"
            snapshot_file.write_text(raw_text, encoding="utf-8")
            logger.info("Saved Ollama raw response to %s", snapshot_file)
        except Exception:
            logger.warning("Failed to snapshot Ollama raw response", exc_info=True)

        if resp.status_code != 200:
            logger.error("Ollama non-200 response body: %s", raw_text)
            raise OllamaError(f"HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        # If Ollama returned an empty response but provided thinking, attempt salvage.
        try:
            if isinstance(data, dict):
                resp_text = data.get("response", "")
                thinking = data.get("thinking", "")
                done_reason = data.get("done_reason")
                if (isinstance(resp_text, str) and resp_text.strip() == "" 
                        and isinstance(thinking, str) and thinking.strip()):
                    logger.warning("Ollama returned empty response with thinking present (done_reason=%s). Attempting salvage.", done_reason)

                    import re, json as _json

                    # Extract sentences; prefer CJK-only short sentences; de-duplicate
                    candidates = []
                    seen = set()

                    def _is_cjk_sentence(s: str) -> bool:
                        if not re.search(r"[\u4e00-\u9fff]", s):
                            return False
                        if re.search(r"[A-Za-z]", s):
                            return False
                        return True

                    def _norm(s: str) -> str:
                        return re.sub(r"\s+", "", s)
                    for line in thinking.splitlines():
                        m = re.match(r"\s*\d+\.\s*\"([^\"]+)\"", line)
                        if m:
                            text = m.group(1).strip()
                            if text and text.lower() != 'none' and _is_cjk_sentence(text):
                                key = _norm(text)
                                if key not in seen:
                                    seen.add(key)
                                    # ensure terminal punctuation
                                    if not re.search(r"[。！？]$", text):
                                        text = text + "。"
                                    candidates.append(text)
                        if len(candidates) >= 5:
                            break

                    # Secondary heuristic: look for lines that look like Chinese sentences without quotes
                    if len(candidates) < 5:
                        for line in thinking.splitlines():
                            s = line.strip()
                            if not s or re.search(r"(?i)count|characters|user_input|dialogue|context|nurse|patient", s):
                                continue
                            # Accept likely sentence lines that end with 。！？ or contain中文
                            if _is_cjk_sentence(s):
                                # strip leading bullets
                                s = re.sub(r"^\s*\d+\.\s*", "", s)
                                s = s.strip('"')
                                if s and s.lower() != 'none':
                                    if not re.search(r"[。！？]$", s):
                                        s = s + "。"
                                    key = _norm(s)
                                    if key not in seen:
                                        seen.add(key)
                                        candidates.append(s)
                            if len(candidates) >= 5:
                                break

                    candidates = candidates[:5]

                    if candidates:
                        salvaged = {
                            "reasoning": "salvaged from thinking",
                            "character_consistency_check": "YES",
                            "context_classification": "unspecified",
                            "confidence": "0.60",
                            "responses": candidates,
                            "state": "NORMAL",
                            "dialogue_context": "SALVAGED_FROM_THINKING",
                            "state_reasoning": "Empty response with thinking; salvaged candidates",
                        }
                        salvaged_str = _json.dumps(salvaged, ensure_ascii=False)
                        logger.info("Salvaged JSON from thinking: %s", salvaged_str)
                        return salvaged_str
        except Exception:
            logger.warning("Failed to salvage from thinking", exc_info=True)

        # If still empty response, perform one lightweight retry with compact options
        try:
            if isinstance(data, dict) and isinstance(data.get("response", ""), str) and data.get("response", "").strip() == "":
                logger.info("Empty response after first call. Retrying Ollama with compact options …")
                retry_payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        **self.default_options,
                        "temperature": 0.5,
                        "top_p": 0.7,
                        "num_predict": max(int(self.default_options.get("num_predict", 768)) + 128, 768),
                        "reasoning": {"effort": "low"},
                    },
                }
                resp2 = requests.post(url, json=retry_payload, timeout=self.timeout)
                raw2 = resp2.text if hasattr(resp2, "text") else ""
                logger.debug("[Retry] Ollama raw response length: %s", len(raw2))
                logger.debug("[Retry] Ollama raw response (first 500 chars): %s", raw2[:500])
                try:
                    snapshot_dir = Path("logs") / "debug" / "ollama_raw"
                    snapshot_dir.mkdir(parents=True, exist_ok=True)
                    snapshot_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    snapshot_file = snapshot_dir / f"{snapshot_name}_retry_{uuid.uuid4().hex}.json"
                    snapshot_file.write_text(raw2, encoding="utf-8")
                    logger.info("Saved Ollama raw response (retry) to %s", snapshot_file)
                except Exception:
                    logger.warning("Failed to snapshot Ollama raw response (retry)", exc_info=True)

                if resp2.status_code != 200:
                    logger.error("[Retry] Ollama non-200 response: %s", raw2)
                else:
                    data2 = resp2.json()
                    if isinstance(data2, dict):
                        r2 = data2.get("response", "")
                        if isinstance(r2, str) and r2.strip():
                            return r2
                        # Last-chance salvage from thinking
                        t2 = data2.get("thinking", "")
                        if isinstance(t2, str) and t2.strip():
                            try:
                                import re, json as _json
                                candidates = []
                                seen = set()
                                def _is_cjk_sentence(s: str) -> bool:
                                    return bool(re.search(r"[\u4e00-\u9fff]", s)) and not bool(re.search(r"[A-Za-z]", s))
                                def _norm(s: str) -> str:
                                    import re as _re
                                    return _re.sub(r"\s+", "", s)
                                for line in t2.splitlines():
                                    m = re.match(r"\s*\d+\.\s*\"([^\"]+)\"", line)
                                    if m:
                                        txt = m.group(1).strip()
                                        if txt and _is_cjk_sentence(txt):
                                            if not re.search(r"[。！？]$", txt):
                                                txt += "。"
                                            key = _norm(txt)
                                            if key not in seen:
                                                seen.add(key); candidates.append(txt)
                                    if len(candidates) >= 5:
                                        break
                                if candidates:
                                    saved = {
                                        "reasoning": "salvaged from thinking (retry)",
                                        "character_consistency_check": "YES",
                                        "context_classification": "unspecified",
                                        "confidence": "0.60",
                                        "responses": candidates[:5],
                                        "state": "NORMAL",
                                        "dialogue_context": "SALVAGED_FROM_THINKING",
                                        "state_reasoning": "Empty response; salvaged on retry",
                                    }
                                    return _json.dumps(saved, ensure_ascii=False)
                            except Exception:
                                logger.warning("Retry salvage failed", exc_info=True)
        except Exception:
            logger.warning("Retry path raised an exception", exc_info=True)
        if not isinstance(data, dict):
            raise OllamaError("Unexpected Ollama response format")

        if data.get("error"):
            raise OllamaError(str(data["error"]))

        # Non-stream responses include the entire text under "response".
        response_text = data.get("response", "")
        if not isinstance(response_text, str):
            response_text = str(response_text)

        return response_text
