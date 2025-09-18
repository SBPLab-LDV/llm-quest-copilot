#!/usr/bin/env python3
"""Sensitive question rewrite flow for Gemini refusals.

When Gemini declines to answer a nurse question because of policy filters, we need a
secondary prompt that:
- Audits the caregiver's wording for policy triggers
- Suggests a compliant rewrite that keeps the clinical intent intact
- Provides a short reassurance so the nurse understands why wording changed

This module encapsulates that logic as a DSPy Chain-of-Thought program so it can be
plugged into :class:`OptimizedDialogueManagerDSPy` without an extra LLM dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import dspy

logger = logging.getLogger(__name__)


class SensitiveQuestionRewriteSignature(dspy.Signature):
    """Ask the model to determine if a caregiver question should be rewritten.

    Output fields follow a simple contract understood by
    :meth:`OptimizedDialogueManagerDSPy._attempt_sensitive_rewrite`:
    - ``sensitivity_flag`` must be ``YES``/``NO`` (or equivalent) so we know whether to
      dispatch the rewritten question.
    - ``rewritten_question`` supplies the safe phrasing only when a rewrite is needed.
    - ``sensitivity_reason`` explains which policy topic was triggered.
    - ``reassurance_message`` is shown to the caregiver for additional context.
    """

    policy_brief = dspy.InputField(desc="Safety guidelines the question must comply with")
    original_question = dspy.InputField(desc="Original caregiver wording")
    conversation_summary = dspy.InputField(desc="Recent conversation snippets for context")
    character_name = dspy.InputField(desc="Patient name")
    character_persona = dspy.InputField(desc="Patient persona summary")

    analysis = dspy.OutputField(desc="Detailed safety analysis steps and policy checks")
    sensitivity_flag = dspy.OutputField(desc="YES/NO if rewrite is required. Prefer YES/NO.")
    rewritten_question = dspy.OutputField(desc="Safe rewritten question. Empty if no rewrite.")
    sensitivity_reason = dspy.OutputField(desc="Concise explanation of the policy risk")
    reassurance_message = dspy.OutputField(desc="Friendly reminder for the caregiver")


@dataclass
class RewriteResult:
    """Typed container returned by :class:`SensitiveQuestionRewriteModule`."""

    sensitivity_flag: str
    rewritten_question: str
    sensitivity_reason: str
    reassurance_message: str
    analysis: str


class SensitiveQuestionRewriteModule:
    """Lightweight wrapper around a DSPy Chain-of-Thought rewritting program."""

    DEFAULT_POLICY = (
        "請扮演臨床安全顧問，協助護理人員將問題改寫為符合醫療政策且尊重病患的表達。\n"
        "- 僅處理合法、安全的醫療照護請求。\n"
        "- 禁止提供違規藥品、違反醫囑或更改病歷的指示。\n"
        "- 若原始提問已合規，回覆 NO 並保持空白的改寫欄位。\n"
        "- 如需改寫，保留原意並加入明確的安全說明。\n"
        "- 保持語氣溫和，避免指責。"
    )

    def __init__(self, config: Optional[Dict[str, object]] = None) -> None:
        self.config = config or {}
        use_cot = self.config.get("use_cot", True)
        chain_cls = dspy.ChainOfThought if use_cot else dspy.Predict
        self.program = chain_cls(SensitiveQuestionRewriteSignature)
        self.logger = logging.getLogger(self.__class__.__name__)

    def rewrite(
        self,
        original_question: str,
        conversation_summary: str = "",
        character_name: str = "",
        character_persona: str = "",
    ) -> Optional[RewriteResult]:
        """Rewrite a caregiver question if it risks a Gemini policy refusal.

        Returns ``None`` if the LM call fails or inputs are empty, so callers can skip the
        sensitive-flow without crashing.
        """

        original_question = (original_question or "").strip()
        if not original_question:
            self.logger.warning("Sensitive rewrite skipped: empty original question")
            return None

        try:
            policy_brief = self.config.get("policy_brief", self.DEFAULT_POLICY)
            context = conversation_summary.strip() or "(無近期對話摘要)"
            patient_name = character_name or "病患"
            persona = character_persona or "住院中的病患"

            prediction = self.program(
                policy_brief=policy_brief,
                original_question=original_question,
                conversation_summary=context,
                character_name=patient_name,
                character_persona=persona,
            )

            # Normalize fields to strings for downstream checks.
            sensitivity_flag = str(getattr(prediction, "sensitivity_flag", "")).strip()
            rewritten_question = str(getattr(prediction, "rewritten_question", "")).strip()
            reason = str(getattr(prediction, "sensitivity_reason", "")).strip()
            reassurance = str(getattr(prediction, "reassurance_message", "")).strip()
            analysis = str(getattr(prediction, "analysis", "")).strip()

            return RewriteResult(
                sensitivity_flag=sensitivity_flag,
                rewritten_question=rewritten_question,
                sensitivity_reason=reason,
                reassurance_message=reassurance,
                analysis=analysis,
            )

        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error("Sensitive rewrite invocation failed: %s", exc, exc_info=True)
            return None
