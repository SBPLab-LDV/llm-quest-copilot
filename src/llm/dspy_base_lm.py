"""Common DSPy language-model helpers for provider-specific adapters."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import dspy

logger = logging.getLogger(__name__)
logger.propagate = True


class DSPyResponse:
    """Simple response wrapper used by legacy code paths."""

    def __init__(self, text: str):
        self.text = text

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"DSPyResponse(text='{self.text[:50]}...')"


_DEBUG_LOG_DIR = Path("logs") / "debug"
_DEBUG_LOG_HANDLER: Optional[logging.FileHandler] = None
_ROOT_DEBUG_LOG_HANDLER: Optional[logging.FileHandler] = None


def start_dspy_debug_log(tag: Optional[str] = None) -> Optional[Path]:
    """Create a timestamped DSPy debug log file for the current session."""

    global _DEBUG_LOG_HANDLER, _ROOT_DEBUG_LOG_HANDLER

    try:
        _DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tag_suffix = ""
        if tag:
            safe_tag = "".join(c if c.isalnum() or c in {"-", "_"} else '_' for c in tag)
            if safe_tag:
                tag_suffix = f"_{safe_tag}"

        debug_log_path = _DEBUG_LOG_DIR / f"{timestamp}{tag_suffix}_dspy_internal_debug.log"

        handler = logging.FileHandler(debug_log_path, mode='w', encoding='utf-8')
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        if _DEBUG_LOG_HANDLER:
            logger.removeHandler(_DEBUG_LOG_HANDLER)
            try:
                _DEBUG_LOG_HANDLER.close()
            except Exception:
                logger.warning("Failed to close previous DSPy debug log handler", exc_info=True)

        if _ROOT_DEBUG_LOG_HANDLER:
            root_logger = logging.getLogger()
            root_logger.removeHandler(_ROOT_DEBUG_LOG_HANDLER)
            try:
                _ROOT_DEBUG_LOG_HANDLER.close()
            except Exception:
                logger.warning("Failed to close previous root debug log handler", exc_info=True)

        _DEBUG_LOG_HANDLER = handler
        logger.addHandler(handler)

        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        _ROOT_DEBUG_LOG_HANDLER = handler
        logger.info("DSPy debug log started at %s", debug_log_path)
        return debug_log_path

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to start DSPy debug log: %s", exc, exc_info=True)
        return None


class BaseDSPyLM(dspy.LM):
    """Shared implementation for DSPy-compatible language models."""

    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        temperature: float = 0.9,
        top_p: float = 0.8,
        top_k: int = 40,
        max_output_tokens: int = 2048,
        **kwargs,
    ) -> None:
        super().__init__(model=model, **kwargs)

        self.provider_name = provider_name
        self.model_name = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_output_tokens = max_output_tokens

        # Runtime statistics
        self.call_count = 0
        self.total_tokens = 0
        self.error_count = 0
        self.total_latency = 0.0

        logger.info(
            "DSPy %s 適配器初始化完成：模型=%s, 溫度=%s",
            self.provider_name,
            model,
            temperature,
        )

    # ------------------------------------------------------------------
    # DSPy LM interface
    # ------------------------------------------------------------------
    def forward(self, prompt=None, messages=None, **kwargs):  # type: ignore[override]
        logger.info("🔄 DSPy forward() 調用")
        logger.info("  - prompt: %s...", prompt[:100] if isinstance(prompt, str) else None)
        logger.info("  - messages: %s", messages)
        logger.info("  - kwargs: %s", list(kwargs.keys()))

        try:
            if prompt is not None:
                input_text = prompt
            elif messages is not None:
                input_text = self._convert_messages_to_prompt(messages)
            else:
                raise ValueError("必須提供 prompt 或 messages")

            logger.info("  - 處理後輸入: %s...", input_text[:200])
            response_text = self._call_model(input_text, **kwargs)
            logger.info("🔄 forward() %s 回應長度: %s", self.provider_name, len(response_text))
            logger.info("🔄 forward() %s 回應內容: %s...", self.provider_name, response_text[:200])
            return response_text

        except Exception as exc:
            logger.error("❌ DSPy forward() 失敗: %s", exc)
            logger.error("完整錯誤: %s", self._format_exception())
            raise

    def generate(self, prompt: str, **kwargs) -> str:  # type: ignore[override]
        logger.info("🔄 DSPy generate() 調用，prompt 長度: %s", len(prompt))
        logger.info("🔄 DSPy generate() prompt 內容: %s...", prompt[:200])
        response = self._call_model(prompt, **kwargs)
        logger.info("🔄 DSPy generate() 返回，response 長度: %s", len(response))
        logger.info("🔄 DSPy generate() 返回內容: %s...", response[:200])

        if not isinstance(response, str):
            logger.warning("⚠️ generate() 返回的不是字符串類型: %s", type(response))
            response = str(response)
        return response

    def basic_request(self, prompt: str, **kwargs) -> str:  # type: ignore[override]
        return self._call_model(prompt, **kwargs)

    def __call__(self, prompt: Union[str, List[str]] = None, **kwargs):  # type: ignore[override]
        start_time = time.time()

        logger.critical("🚨 DSPy%sLM.__call__ 被調用!", self.provider_name)
        logger.critical("  - prompt type: %s", type(prompt))
        logger.critical(
            "  - prompt: %s...",
            prompt[:100] if isinstance(prompt, str) else prompt,
        )
        logger.critical("  - kwargs keys: %s", list(kwargs.keys()))

        try:
            # DSPy 3.0 支援: 如果有 messages 但沒有 prompt，從 messages 構建 prompt
            if prompt is None and 'messages' in kwargs:
                messages = kwargs.pop('messages')
                prompt = self._convert_messages_to_prompt(messages)
                logger.critical("  - 從 messages 構建 prompt: %s...", prompt[:200])

            if isinstance(prompt, str):
                response = self._call_model(prompt, **kwargs)
                self._update_stats(start_time, success=True)

                # DSPy 3.0 兼容性修復 - 返回列表[str] 以避免被當作字符序列處理
                logger.critical("🔧 Adapter 兼容性修復 - 返回列表[str] 以避免截斷")
                logger.critical(f"  - 回應長度: {len(response)} 字符")
                logger.critical(f"  - 回應前100字符: {response[:100]}...")
                return [response]

            if isinstance(prompt, list):
                responses = [self._call_model(p, **kwargs) for p in prompt]
                self._update_stats(start_time, success=True, batch_size=len(prompt))
                return responses

            raise ValueError(f"不支持的 prompt 類型: {type(prompt)}")

        except Exception:
            self._update_stats(start_time, success=False)
            logger.error("DSPy %s 調用失敗", self.provider_name, exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _convert_messages_to_prompt(self, messages) -> str:
        if isinstance(messages, list):
            prompt_parts = []
            for msg in messages:
                if isinstance(msg, dict) and 'content' in msg:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    if role == 'system':
                        prompt_parts.append(f"System: {content}")
                    elif role == 'user':
                        prompt_parts.append(f"User: {content}")
                    elif role == 'assistant':
                        prompt_parts.append(f"Assistant: {content}")
                    else:
                        prompt_parts.append(content)
                else:
                    prompt_parts.append(str(msg))
            return "\n\n".join(prompt_parts)
        return str(messages)

    def _clean_markdown_json(self, response: str) -> str:
        import re

        cleaned = re.sub(r'^```(?:json)?\s*\n', '', response.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'\n```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
        cleaned = cleaned.strip()

        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            logger.warning("清理後的回應不是有效 JSON，返回原始回應")
            return response

    def _normalize_json_response(self, text: str) -> str:
        try:
            s = text.strip()
            if not (s.startswith('{') and s.endswith('}')):
                return text

            obj = json.loads(s)
            if not isinstance(obj, dict):
                return text

            # Fill missing fields with defaults to prevent JSONAdapter failures.
            # Note: Unified DSPy signature expects additional fields; keeping this
            # centralized avoids brittle downstream parsing.
            required = [
                "reasoning",
                "character_consistency_check",
                "context_classification",
                "confidence",
                "responses",
                "core_question",
                "prior_facts",
                "context_judgement",
            ]

            defaults = {
                "reasoning": "",
                "character_consistency_check": "UNKNOWN",
                "context_classification": "unspecified",
                "confidence": "0.00",
                "responses": [],
                "core_question": "",
                "prior_facts": [],
                "context_judgement": {},
            }

            for key in required:
                if key not in obj or obj[key] in (None, ""):
                    obj[key] = defaults[key]

            if isinstance(obj.get("responses"), str):
                try:
                    maybe_list = json.loads(obj["responses"])
                    if isinstance(maybe_list, list):
                        obj["responses"] = [str(x) for x in maybe_list[:5]]
                    else:
                        obj["responses"] = [obj["responses"]]
                except Exception:
                    obj["responses"] = [obj["responses"]]
            elif isinstance(obj.get("responses"), list):
                obj["responses"] = [str(x) for x in obj["responses"][:5]]
            else:
                obj["responses"] = [str(obj["responses"])]

            if not isinstance(obj.get("prior_facts"), list):
                obj["prior_facts"] = []
            if not isinstance(obj.get("context_judgement"), dict):
                obj["context_judgement"] = {}

            try:
                conf = float(obj.get("confidence", "0.90"))
            except Exception:
                conf = 0.90
            obj["confidence"] = f"{conf:.2f}"

            normalized = json.dumps(obj, ensure_ascii=False)
            return normalized

        except Exception:  # pragma: no cover - return original on failure
            logger.warning("JSON normalization failed", exc_info=True)
            return text

    def _update_stats(self, start_time: float, success: bool, batch_size: int = 1) -> None:
        elapsed = time.time() - start_time
        self.total_latency += elapsed
        if not success:
            self.error_count += 1

    def reset_stats(self) -> None:
        self.call_count = 0
        self.total_tokens = 0
        self.error_count = 0
        self.total_latency = 0.0

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = (
            (self.total_latency / self.call_count) if self.call_count else 0.0
        )
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "avg_latency": avg_latency,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_output_tokens": self.max_output_tokens,
        }

    def _format_exception(self) -> str:
        import traceback

        return traceback.format_exc()

    # ------------------------------------------------------------------
    # Provider hook
    # ------------------------------------------------------------------
    def _call_model(self, prompt: str, **kwargs) -> str:
        """Invoke the underlying provider. Subclasses must implement."""

        raise NotImplementedError
