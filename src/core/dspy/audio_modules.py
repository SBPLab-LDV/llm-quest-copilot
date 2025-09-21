"""DSPy modules for audio prompt composition and post-processing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import dspy
import yaml

from .signatures import AudioDisfluencyChatSignature

logger = logging.getLogger(__name__)


class AudioPromptComposerModule(dspy.Module):
    """Assemble system/user prompts for audio disfluency tasks."""

    def __init__(self, template_path: Optional[Path] = None) -> None:
        super().__init__()
        self.template_path = template_path or Path("prompts/templates/audio_disfluency_template.yaml")
        self._system_cached: Optional[str] = None
        self.signature = AudioDisfluencyChatSignature

    def _load_system_body(self) -> str:
        if self._system_cached is not None:
            return self._system_cached
        try:
            with self.template_path.open('r', encoding='utf-8') as file:
                data = yaml.safe_load(file) or {}
            self._system_cached = data.get('audio_disfluency', '')
        except FileNotFoundError:
            logger.warning("Audio template not found: %s", self.template_path)
            self._system_cached = ''
        return self._system_cached

    def forward(
        self,
        *,
        character_profile: str,
        conversation_history: str,
        available_contexts: str,
        template_rules: str,
        option_count: int,
    ) -> dspy.Prediction:
        system_body = self._load_system_body()
        system_prompt = system_body

        user_sections = []
        if character_profile:
            user_sections.append(f"【角色摘要】\n{character_profile}")
        if conversation_history:
            user_sections.append(f"【近期對話】\n{conversation_history}")
        if available_contexts:
            user_sections.append(f"【可用情境】\n{available_contexts}")
        if template_rules:
            user_sections.append(f"【輸出規則提醒】\n{template_rules}")
        user_sections.append(f"請依規則輸出 {option_count} 個具體完整句子。")
        user_prompt = "\n\n".join(section for section in user_sections if section)

        return dspy.Prediction(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


_composer_singleton: Optional[AudioPromptComposerModule] = None


def get_audio_prompt_composer() -> AudioPromptComposerModule:
    global _composer_singleton
    if _composer_singleton is None:
        _composer_singleton = AudioPromptComposerModule()
    return _composer_singleton


__all__ = [
    'AudioPromptComposerModule',
    'get_audio_prompt_composer',
]

# ---------------------------------------------------------------------------
# Minimal post-processing (normalize) stub used by server gating
# ---------------------------------------------------------------------------

class AudioDisfluencyPostModule:
    """Minimal normalizer to ensure {original, options} JSON shape.

    This is a lightweight, deterministic fallback so the server import works
    even when DSPy-based normalization experiments are disabled by default.
    """

    def __init__(self) -> None:
        pass

    def _clean_fences(self, text: str) -> str:
        s = (text or '').strip()
        if s.startswith('```json'):
            s = s[7:]
        if s.endswith('```'):
            s = s[:-3]
        return s.strip()

    def normalize(
        self,
        *,
        system_prompt: str = '',
        user_prompt: str = '',
        conversation_history: str = '',
        raw_transcription: str = '',
        trace_id: str = '',
    ) -> dict:
        import json
        cleaned = self._clean_fences(raw_transcription or '')

        def _pack(original: str, options: list[str]):
            safe_options = [str(x).strip() for x in (options or []) if str(x).strip()]
            if not safe_options and original:
                safe_options = [original]
            payload = {"original": str(original or '').strip(), "options": safe_options[:5]}
            return {"normalized_json": json.dumps(payload, ensure_ascii=False)}

        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                original = obj.get('original') or obj.get('text') or obj.get('transcript') or ''
                options = obj.get('options')
                if not isinstance(options, list):
                    options = [original] if original else []
                return _pack(original, options)
            # If it's a list, take first as original
            if isinstance(obj, list) and obj:
                return _pack(str(obj[0]), list(obj))
        except Exception:
            pass

        # Fallback: treat the whole string as original
        return _pack(cleaned, [cleaned] if cleaned else [])


_post_singleton: Optional[AudioDisfluencyPostModule] = None


def get_audio_disfluency_module() -> AudioDisfluencyPostModule:
    global _post_singleton
    if _post_singleton is None:
        _post_singleton = AudioDisfluencyPostModule()
    return _post_singleton


__all__ += [
    'AudioDisfluencyPostModule',
    'get_audio_disfluency_module',
]
