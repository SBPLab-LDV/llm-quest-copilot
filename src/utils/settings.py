from __future__ import annotations

import os
from typing import Any, Dict, Optional

import yaml


DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def normalize_settings(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize raw config/config.yaml into a consistent structure.

    This function is intentionally conservative: it preserves current behavior
    by mapping legacy keys into the new structure when the new keys are absent.
    """

    raw = _ensure_dict(raw)
    raw_has_llm = isinstance(raw.get("llm"), dict)

    llm = _ensure_dict(raw.get("llm"))
    llm_gemini = _ensure_dict(llm.get("gemini"))
    llm_generation = _ensure_dict(llm.get("generation"))

    # Legacy: google_api_key at root.
    legacy_api_key = raw.get("google_api_key")
    if not llm_gemini.get("api_key") and legacy_api_key:
        llm_gemini["api_key"] = legacy_api_key

    # Legacy: model config stored under dspy.*.
    # Safety: only inherit this if the user has opted into the new `llm:` schema
    # (otherwise we'd change runtime behavior compared to the historical hardcode).
    dspy = _ensure_dict(raw.get("dspy"))
    if raw_has_llm and not llm_gemini.get("model") and dspy.get("model"):
        llm_gemini["model"] = dspy.get("model")

    llm.setdefault("provider", llm.get("provider") or dspy.get("provider") or "gemini")
    llm["gemini"] = llm_gemini
    llm["generation"] = llm_generation

    speech = _ensure_dict(raw.get("speech"))
    speech_google = _ensure_dict(_ensure_dict(speech.get("google_cloud_speech")))
    speech["google_cloud_speech"] = speech_google

    normalized = dict(raw)
    normalized["llm"] = llm
    normalized["speech"] = speech
    normalized["dspy"] = dspy
    normalized["_meta"] = {"raw_has_llm": raw_has_llm}
    return normalized


def load_settings(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
    except FileNotFoundError:
        raw = {}
    except yaml.YAMLError:
        raw = {}
    return normalize_settings(raw)


def get_gemini_api_key(settings: Dict[str, Any]) -> Optional[str]:
    llm = _ensure_dict(settings.get("llm"))
    gemini = _ensure_dict(llm.get("gemini"))
    api_key = gemini.get("api_key") or settings.get("google_api_key")
    if api_key:
        return str(api_key)
    env_key = os.getenv("GOOGLE_API_KEY")
    if env_key:
        return env_key
    return None


def get_gemini_model(settings: Dict[str, Any]) -> str:
    llm = _ensure_dict(settings.get("llm"))
    gemini = _ensure_dict(llm.get("gemini"))
    model = gemini.get("model")
    if model:
        return str(model)
    return DEFAULT_GEMINI_MODEL
