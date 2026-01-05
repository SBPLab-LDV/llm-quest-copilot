"""Audio prompt utilities for DSPy integration."""

import logging
from typing import List, Optional

from ..character import Character
from ..scenario_manager import get_scenario_manager

logger = logging.getLogger(__name__)

# 保留作為 fallback
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


def build_available_audio_contexts(
    previous_context: Optional[str] = None,
    previous_speaker: Optional[str] = None,
    max_items: int = 3
) -> str:
    """動態選擇可用情境（整合 ScenarioManager）

    Args:
        previous_context: 上一輪推理出的情境（優先列出）
        previous_speaker: 上一輪推理出的 speaker（用於過濾相關情境）
        max_items: 最多列出幾個情境

    Returns:
        格式化的情境列表字串
    """
    try:
        scenario_manager = get_scenario_manager()
        available = list(scenario_manager.scenarios.keys())

        if not available:
            raise ValueError("No scenarios loaded")

        prioritized: List[str] = []

        # 1. 若有上一輪情境，優先列出
        if previous_context and previous_context in available:
            prioritized.append(previous_context)

        # 2. 若有上一輪 speaker，找出該 speaker 相關的情境
        if previous_speaker and previous_speaker in scenario_manager.speaker_index:
            speaker_scenarios = scenario_manager.speaker_index[previous_speaker]
            for ctx in speaker_scenarios:
                if ctx not in prioritized:
                    prioritized.append(ctx)
                if len(prioritized) >= max_items:
                    break

        # 3. 補充其他情境
        for ctx in available:
            if ctx not in prioritized:
                prioritized.append(ctx)
            if len(prioritized) >= max_items:
                break

        lines = [f"- {ctx}" for ctx in prioritized[:max_items]]
        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"ScenarioManager 載入失敗，使用 fallback: {e}")
        # Fallback to original behavior
        lines = [f"- {label}: {desc}" for label, desc in DEFAULT_AUDIO_CONTEXT_PRIORITY[:max_items]]
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
    """Return a concise runtime rule string for audio tasks.

    Keep only output shape + minimal enforcement to lower token usage.
    """
    return (
        # Output shape
        "請輸出單一合法 JSON（不得使用 markdown），包含 'original' 與 'options'；"
        f"'options' 為長度 {option_count} 的完整句子陣列（繁體中文、單句）。"
        # Core enforcement
        " 'original' 需保留關鍵詞，對破碎輸入可溫和重建但不得臆造新意；"
        " 若 original 以逗號/頓號分隔多個短語，將每個短語視為一個『意圖』，前若干句需逐一直接對齊各意圖（直述或請求評估），不得以與意圖無關的泛用句取代；"
        " 如動作/處置與【角色摘要】或【近期對話】的限制（不可說話/吞嚥/下床/口進食/鼻胃管/氣切）矛盾，請改為『請求評估/如何安全地…』的表達。"
    )


__all__ = [
    'format_history_for_audio',
    'build_available_audio_contexts',
    'summarize_character',
    'build_audio_template_rules',
    'DEFAULT_AUDIO_CONTEXT_PRIORITY',
]
