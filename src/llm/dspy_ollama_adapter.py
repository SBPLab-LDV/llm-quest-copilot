"""DSPy Ollama 適配器。"""

from __future__ import annotations

import logging
import json
from typing import Any, Dict, Optional

from .dspy_base_lm import BaseDSPyLM, DSPyResponse, start_dspy_debug_log
from .ollama_client import OllamaClient
from ..core.dspy.config import get_config


logger = logging.getLogger(__name__)
logger.propagate = True


OPTION_MAP = {
    "temperature": "temperature",
    "top_p": "top_p",
    "top_k": "top_k",
    "max_output_tokens": "num_predict",
}


class DSPyOllamaLM(BaseDSPyLM):
    """將 Ollama 模型包裝為 DSPy LM。"""

    def __init__(
        self,
        model: str = "gpt-oss:20b",
        base_url: str = "http://127.0.0.1:11434",
        timeout: int = 120,
        temperature: float = 0.9,
        top_p: float = 0.8,
        top_k: int = 40,
        max_output_tokens: int = 1024,
        default_options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            provider_name="Ollama",
            model=model,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )

        base_options = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "num_predict": max_output_tokens,
            # Try to limit externalized chain-of-thought usage if model supports it
            "reasoning": {"effort": "low"},
        }
        # Merge and drop None values
        merged_options = {
            key: value
            for key, value in {**base_options, **(default_options or {})}.items()
            if value is not None
        }

        self.ollama_client = OllamaClient(
            base_url=base_url,
            model=model,
            timeout=timeout,
            default_options=merged_options,
        )

    # ------------------------------------------------------------------
    # Provider hook
    # ------------------------------------------------------------------
    def _call_model(self, prompt: str, **kwargs) -> str:
        self.call_count += 1

        try:
            logger.debug("DSPy -> Ollama 調用 #%s", self.call_count)
            logger.debug("提示長度: %s 字符", len(prompt))

            logger.info("=== OLLAMA PROMPT INPUT (Call #%s) ===", self.call_count)
            logger.info("Prompt length: %s characters", len(prompt))
            logger.info("Full prompt content:\n%s", prompt)
            logger.info("Call kwargs: %s", kwargs)
            logger.info("=== END OLLAMA PROMPT INPUT ===")

            call_options: Dict[str, Any] = {}
            for key, option_name in OPTION_MAP.items():
                if key in kwargs and kwargs[key] is not None:
                    call_options[option_name] = kwargs.pop(key)

            if kwargs:
                logger.debug("忽略 Ollama 不支援的額外參數: %s", list(kwargs.keys()))

            response = self.ollama_client.generate_response(prompt, **call_options)

            logger.info("=== OLLAMA RESPONSE OUTPUT (Call #%s) ===", self.call_count)
            logger.info("Response length: %s characters", len(response))
            logger.info("Full response content:\n%s", response)
            logger.info("=== END OLLAMA RESPONSE OUTPUT ===")

            # 去除多餘的空白和換行符
            response = response.strip()

            # 嘗試清理 markdown 格式
            cleaned = self._clean_markdown_json(response)
            if cleaned != response:
                logger.info(
                    "🧹 清理 markdown 格式: %s -> %s 字符",
                    len(response),
                    len(cleaned),
                )
                logger.info("清理後完整內容: %s", cleaned)
                response = cleaned

            # 正規化 JSON，補齊缺失欄位並限制 responses 最多 5 條
            normalized = self._normalize_json_response(response)
            if normalized != response:
                logger.info("🔧 已正規化 JSON 輸出（補齊缺失欄位/格式化）")
            return normalized

        except Exception as exc:
            self.error_count += 1
            logger.error(
                "Ollama 調用失敗 (第 %s 次): %s", self.call_count, exc, exc_info=True
            )

            error_payload: Dict[str, Any] = {
                "reasoning": f"Ollama invocation failed: {type(exc).__name__}",
                "character_consistency_check": "UNKNOWN",
                "context_classification": "error",
                "confidence": "0.00",
                "responses": [f"OllamaError[{type(exc).__name__}]: {exc}"],
                "state": "ERROR",
                "dialogue_context": "OLLAMA_EXCEPTION",
                "state_reasoning": "Ollama API raised an exception",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
            return json.dumps(error_payload, ensure_ascii=False)

    @classmethod
    def from_config(
        cls, config_override: Optional[Dict[str, Any]] = None
    ) -> "DSPyOllamaLM":
        config = get_config()
        model_config = config.get_model_config()
        # Ensure provider-specific defaults override shared ones
        model_config.pop('provider', None)
        if config_override:
            model_config.update(config_override)
        return cls(**model_config)


def create_dspy_lm(config_override: Optional[Dict[str, Any]] = None) -> DSPyOllamaLM:
    return DSPyOllamaLM.from_config(config_override)


__all__ = ["DSPyOllamaLM", "DSPyResponse", "start_dspy_debug_log", "create_dspy_lm"]
