"""DSPy Gemini 適配器。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from .dspy_base_lm import BaseDSPyLM, DSPyResponse, start_dspy_debug_log
from .gemini_client import GeminiClient
from ..core.dspy.config import get_config

logger = logging.getLogger(__name__)
logger.propagate = True


class DSPyGeminiLM(BaseDSPyLM):
    """將 GeminiClient 包裝為 DSPy LM 介面的實作。"""

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.9,
        top_p: float = 0.8,
        top_k: int = 40,
        max_output_tokens: int = 2048,
        **kwargs,
    ) -> None:
        super().__init__(
            provider_name="Gemini",
            model=model,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )
        self.gemini_client = GeminiClient(
            model=model,
            generation_config={
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "max_output_tokens": max_output_tokens,
                # Improve JSON compliance for DSPy JSONAdapter parsing.
                "response_mime_type": "application/json",
            },
        )
        self._last_call_timing: Optional[Dict] = None

    # ------------------------------------------------------------------
    # Provider hook
    # ------------------------------------------------------------------
    def _call_model(self, prompt: str, **kwargs) -> str:
        self.call_count += 1

        try:
            logger.debug("DSPy -> Gemini 調用 #%s", self.call_count)
            logger.debug("提示長度: %s 字符", len(prompt))

            logger.info("=== GEMINI PROMPT INPUT (Call #%s) ===", self.call_count)
            logger.info("Prompt length: %s characters", len(prompt))
            logger.info("Full prompt content:\n%s", prompt)
            logger.info("Call kwargs: %s", kwargs)
            logger.info("=== END GEMINI PROMPT INPUT ===")

            _t_api_start = time.time()
            response = self.gemini_client.generate_response(prompt)
            _t_api_end = time.time()
            _api_duration = round(_t_api_end - _t_api_start, 4)

            self._last_call_timing = {
                "call_number": self.call_count,
                "prompt_chars": len(prompt),
                "response_chars": len(response),
                "api_duration_s": _api_duration,
            }
            logger.info(
                "[Timing] DSPy->Gemini call #%s: prompt=%s chars, response=%s chars, duration=%.3fs",
                self.call_count, len(prompt), len(response), _api_duration,
            )

            logger.info("=== GEMINI RESPONSE OUTPUT (Call #%s) ===", self.call_count)
            logger.info("Response length: %s characters", len(response))
            logger.info("Full response content:\n%s", response)
            logger.info("=== END GEMINI RESPONSE OUTPUT ===")

            cleaned = self._clean_markdown_json(response)
            if cleaned != response:
                logger.info(
                    "🧹 清理 markdown 格式: %s -> %s 字符",
                    len(response),
                    len(cleaned),
                )
                logger.info("清理後完整內容: %s", cleaned)

            normalized = self._normalize_json_response(cleaned)
            logger.debug("Gemini 回應長度: %s 字符", len(normalized))
            return normalized

        except Exception as exc:
            self.error_count += 1
            logger.error(
                "Gemini API 調用失敗 (第 %s 次): %s",
                self.call_count,
                exc,
                exc_info=True,
            )

            error_payload: Dict[str, Any] = {
                "reasoning": f"Gemini invocation failed: {type(exc).__name__}",
                "character_consistency_check": "UNKNOWN",
                "context_classification": "error",
                "confidence": "0.00",
                "responses": [f"GeminiError[{type(exc).__name__}]: {exc}"],
                "state": "ERROR",
                "dialogue_context": "GEMINI_EXCEPTION",
                "state_reasoning": "Gemini API raised an exception",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
            return json.dumps(error_payload, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------
    @classmethod
    def from_config(
        cls, config_override: Optional[Dict[str, Any]] = None
    ) -> "DSPyGeminiLM":
        config = get_config()
        model_config = config.get_model_config()
        model_config.pop('provider', None)
        if config_override:
            model_config.update(config_override)
        return cls(**model_config)


def create_dspy_lm(config_override: Optional[Dict[str, Any]] = None) -> DSPyGeminiLM:
    return DSPyGeminiLM.from_config(config_override)


def test_dspy_gemini_adapter() -> bool:
    logger.info("測試 DSPy Gemini 適配器...")
    try:
        lm = create_dspy_lm()
        test_prompt = "Hello, this is a test prompt."
        response = lm(test_prompt)
        logger.info("測試提示: %s", test_prompt)
        logger.info("回應: %s...", response[:100])
        logger.info("統計信息: %s", lm.get_stats())
        return True
    except Exception as exc:  # pragma: no cover - manual smoke test
        logger.error("DSPy Gemini 適配器測試失敗: %s", exc)
        return False


__all__ = ["DSPyGeminiLM", "DSPyResponse", "start_dspy_debug_log", "create_dspy_lm"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_dspy_gemini_adapter()
