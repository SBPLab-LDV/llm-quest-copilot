"""Audio prompt utilities for DSPy integration."""

from typing import List, Optional

from ..character import Character

DEFAULT_AUDIO_CONTEXT_PRIORITY = [
    ("daily_routine_examples", "病房日常"),
    ("treatment_examples", "治療相關"),
    ("vital_signs_examples", "生命徵象相關"),
]


def _is_system_line(line: str) -> bool:
    if not isinstance(line, str):
        return True
    s = line.strip()
    return s.startswith('[') or s.startswith('(系統)') or s.startswith('[系統]')


def format_history_for_audio(
    conversation_history: Optional[List[str]],
    character_name: Optional[str],
    character_persona: Optional[str],
    max_lines: int = 20,
) -> str:
    """Return trimmed history with persona reminder."""
    persona = character_persona or "病患"
    name = character_name or "病患"
    reminder = f"[角色提醒] 您是 {name}，{persona}。請維持角色設定。"

    if not conversation_history:
        return reminder

    history: List[str] = []
    for entry in conversation_history:
        if isinstance(entry, str) and not _is_system_line(entry):
            trimmed = entry.strip()
            if trimmed:
                history.append(trimmed)
    recent = history[-max_lines:]
    if recent:
        return f"{reminder}\n" + "\n".join(recent)
    return reminder


def build_available_audio_contexts(max_items: int = 2) -> str:
    lines: List[str] = []
    for label, desc in DEFAULT_AUDIO_CONTEXT_PRIORITY[:max_items]:
        lines.append(f"- {label}: {desc}")
    return "\n".join(lines)


def summarize_character(character: Optional[Character]) -> str:
    if character is None:
        return ""

    parts: List[str] = []
    fixed = {}
    floating = {}
    try:
        if isinstance(character.details, dict):
            fixed = character.details.get('fixed_settings') or {}
            floating = character.details.get('floating_settings') or {}
    except Exception:
        fixed = {}
        floating = {}

    name = fixed.get('姓名') or getattr(character, 'name', '病患')
    diagnosis = fixed.get('目前診斷') or fixed.get('診斷')
    stage = fixed.get('診斷分期') or ''
    if diagnosis:
        diag_text = diagnosis if not stage else f"{diagnosis} ({stage})"
        parts.append(f"姓名: {name} / 診斷: {diag_text}")
    else:
        parts.append(f"姓名: {name}")

    treatment_stage = floating.get('目前治療階段') or floating.get('治療階段')
    treatment_status = floating.get('目前治療狀態')
    if treatment_stage or treatment_status:
        text = "目前治療階段: "
        if treatment_stage:
            text += treatment_stage
        if treatment_status and treatment_status != treatment_stage:
            if treatment_stage:
                text += "；狀態: "
            else:
                text += treatment_status
        parts.append(text)

    current_status = floating.get('個案現況')
    if isinstance(current_status, str) and current_status and len(current_status) <= 120:
        parts.append(f"現況: {current_status}")

    persona = getattr(character, 'persona', None)
    if persona:
        parts.append(f"Persona: {persona}")
    goal = getattr(character, 'goal', None)
    if goal:
        parts.append(f"Goal: {goal}")

    return " | ".join(p.strip() for p in parts if p)


def build_audio_template_rules(option_count: int) -> str:
    return (
        "請輸出單一合法 JSON，包含 'original' 與 'options'。"
        f" 'options' 必須為長度 {option_count} 的完整句子陣列，且每句需包含明確的行動/物品/情境，"
        "避免模糊表達（如『我想吃』『我要』『幫我』），內容需貼合住院醫療情境並使用繁體中文；"
        "嚴禁輸出 markdown、程式碼區塊或額外解說。若無法辨識，請提供 {option_count} 句友善的澄清/請求協助之建議。"
    )


__all__ = [
    'format_history_for_audio',
    'build_available_audio_contexts',
    'summarize_character',
    'build_audio_template_rules',
    'DEFAULT_AUDIO_CONTEXT_PRIORITY',
]
