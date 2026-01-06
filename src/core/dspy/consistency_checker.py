#!/usr/bin/env python3
"""
對話一致性檢查器（規則版，零額外 LLM 調用）

提供以下能力：
- 醫療事實提取：fever/pain 初版 + 簡易時間語彙抽取
- 矛盾檢測：症狀狀態翻轉、時間線衝突、自我介紹與通用回應
- 分數與嚴重度：輸出 ConsistencyResult，供上層決策（過濾/提示/僅記錄）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional
import re


@dataclass
class Contradiction:
    type: str
    severity: str
    description: str
    evidence: Dict


@dataclass
class TimelineEvent:
    type: str
    when: str
    norm_time: float  # 0.0 遠古 → 1.0 目前


@dataclass
class ConsistencyResult:
    score: float
    has_contradictions: bool
    contradictions: List[Contradiction]
    facts: Dict
    timeline: List[TimelineEvent]
    severity: str


class MedicalFactTracker:
    """簡易醫療事實抽取器（規則版）"""

    # 注意：避免可選否定導致匹配到肯定句（如 r"不?發燒" 會誤匹配 "發燒"）。
    fever_neg_patterns = [r"沒有發燒", r"沒發燒", r"不發燒", r"沒發熱", r"沒有發熱", r"不發熱"]
    fever_pos_patterns = [r"發燒", r"發熱", r"體溫(有)?升高", r"很熱"]

    pain_neg_patterns = [r"不痛", r"沒有痛", r"沒痛", r"不疼", r"沒有疼", r"沒疼"]
    pain_pos_patterns = [r"痛", r"疼", r"酸痛", r"不舒服"]

    time_tokens = {
        # 近 → 遠（值越大越近）
        r"現在|目前|剛剛|剛才": 1.0,
        r"(今天|今早|今天早上|今天晚上)": 0.9,
        r"(幾|數)小時前": 0.8,
        r"(昨天|昨晚)": 0.6,
        r"前天": 0.5,
        r"(上週|上周)": 0.2,
    }

    def extract(self, text: str) -> Dict:
        text = text or ""
        facts: Dict[str, Optional[bool]] = {
            "fever": None,
            "pain": None,
        }

        # Fever
        if self._match_any(text, self.fever_neg_patterns):
            facts["fever"] = False
        elif self._match_any(text, self.fever_pos_patterns):
            facts["fever"] = True

        # Pain
        if self._match_any(text, self.pain_neg_patterns):
            facts["pain"] = False
        elif self._match_any(text, self.pain_pos_patterns):
            facts["pain"] = True

        return facts

    def extract_timeline(self, text: str) -> List[TimelineEvent]:
        text = text or ""
        events: List[TimelineEvent] = []

        # 偵測「開始」相關的語句，綁定症狀（若能判斷）
        has_start = bool(re.search(r"開始", text))
        topic = "symptom_start" if has_start else "context_time"

        # 依 time_tokens 建立事件
        for pattern, score in self.time_tokens.items():
            if re.search(pattern, text):
                when = re.search(pattern, text).group(0)
                events.append(TimelineEvent(type=topic, when=when, norm_time=score))

        return events

    @staticmethod
    def _match_any(text: str, patterns: List[str]) -> bool:
        return any(re.search(p, text) for p in patterns)


class TimelineValidator:
    """時間線簡易驗證：相同類型事件若多次出現且時間語意相互矛盾則輸出矛盾"""

    def validate(self, timeline: List[TimelineEvent]) -> List[Contradiction]:
        contradictions: List[Contradiction] = []
        # 只在有 2 個以上 symptom_start 事件且時間語彙不同時報告簡易矛盾
        starts = [e for e in timeline if e.type == "symptom_start"]
        if len(starts) >= 2:
            # 若出現同時存在「今天/今早」與「昨晚/昨天」的開始描述，視為可能矛盾
            has_today = any(e.norm_time >= 0.9 for e in starts)
            has_yesterday = any(0.55 <= e.norm_time <= 0.65 for e in starts)
            if has_today and has_yesterday:
                contradictions.append(Contradiction(
                    type="timeline_inconsistency",
                    severity="medium",
                    description="症狀開始時間在 今天 與 昨天/昨晚 之間矛盾",
                    evidence={"events": [e.__dict__ for e in starts]},
                ))
        return contradictions


class ContradictionDetector:
    """事實層級矛盾檢測（fever/pain 初版）"""

    def detect(self, previous_facts: Dict, new_facts: Dict) -> List[Contradiction]:
        contradictions: List[Contradiction] = []
        # Fever flip
        if previous_facts.get("fever") is not None and new_facts.get("fever") is not None:
            if previous_facts["fever"] != new_facts["fever"]:
                contradictions.append(Contradiction(
                    type="fever_state_flip",
                    severity="high",
                    description="發燒狀態前後不一致",
                    evidence={"previous": previous_facts["fever"], "new": new_facts["fever"]},
                ))

        # Pain flip
        if previous_facts.get("pain") is not None and new_facts.get("pain") is not None:
            if previous_facts["pain"] != new_facts["pain"]:
                contradictions.append(Contradiction(
                    type="pain_state_flip",
                    severity="medium",
                    description="疼痛狀態前後不一致",
                    evidence={"previous": previous_facts["pain"], "new": new_facts["pain"]},
                ))

        return contradictions


class DialogueConsistencyChecker:
    """對話一致性檢查器（入口）"""

    self_intro_patterns = [r"我是Patient", r"我是[\u4e00-\u9fa5A-Za-z0-9_]+", r"您好，我是", r"我叫"]
    generic_patterns = [r"我可能沒有完全理解", r"能請您換個方式說明", r"您需要什麼幫助"]

    def __init__(self):
        self.fact_tracker = MedicalFactTracker()
        self.timeline_validator = TimelineValidator()
        self.detector = ContradictionDetector()

    def check_consistency(
        self,
        new_responses: List[str],
        conversation_history: List[str],
        character_context: Optional[Dict] = None,
    ) -> ConsistencyResult:
        # 1) 準備歷史中的上一則病患事實
        last_patient_utt = self._get_last_patient_utterance(conversation_history)
        previous_facts = self.fact_tracker.extract(last_patient_utt)
        previous_timeline = self.fact_tracker.extract_timeline(last_patient_utt)

        # 2) 以第一個新回應為代表抽取新事實（保守策略）
        candidate = (new_responses or [""])[0]
        new_facts = self.fact_tracker.extract(candidate)
        new_timeline = self.fact_tracker.extract_timeline(candidate)

        # 3) 檢測事實矛盾 + 時間線矛盾
        contradictions: List[Contradiction] = []
        contradictions += self.detector.detect(previous_facts, new_facts)
        contradictions += self.timeline_validator.validate(previous_timeline + new_timeline)

        # 4) 內容品質：自我介紹/通用回應
        self_intro_count = sum(1 for r in new_responses if self._match_any(r, self.self_intro_patterns))
        generic_count = sum(1 for r in new_responses if self._match_any(r, self.generic_patterns))

        if self_intro_count:
            contradictions.append(Contradiction(
                type="self_introduction",
                severity="high",
                description="偵測到自我介紹語句",
                evidence={"count": self_intro_count},
            ))
        if generic_count:
            contradictions.append(Contradiction(
                type="generic_response",
                severity="medium",
                description="偵測到通用/退化回應",
                evidence={"count": generic_count},
            ))

        # 5) 評分與嚴重度
        timeline_issues = [c for c in contradictions if c.type == "timeline_inconsistency"]
        fever_issues = [c for c in contradictions if c.type == "fever_state_flip"]
        pain_issues = [c for c in contradictions if c.type == "pain_state_flip"]
        self_intro_issues = [c for c in contradictions if c.type == "self_introduction"]
        generic_issues = [c for c in contradictions if c.type == "generic_response"]

        # 粗略分數（0~1）
        penalties = (
            0.25 * len(timeline_issues)
            + 0.25 * len(fever_issues)
            + 0.15 * len(pain_issues)
            + 0.25 * len(self_intro_issues)
            + 0.10 * len(generic_issues)
        )
        score = max(0.0, 1.0 - min(1.0, penalties))

        # 嚴重度
        if self_intro_issues or fever_issues:
            severity = "high"
        elif timeline_issues or pain_issues or generic_issues:
            severity = "medium"
        else:
            severity = "low"

        result = ConsistencyResult(
            score=score,
            has_contradictions=len(contradictions) > 0,
            contradictions=contradictions,
            facts={"previous": previous_facts, "new": new_facts},
            timeline=previous_timeline + new_timeline,
            severity=severity,
        )
        return result

    @staticmethod
    def _match_any(text: str, patterns: List[str]) -> bool:
        text = text or ""
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _get_last_patient_utterance(history: List[str]) -> str:
        if not history:
            return ""
        # 非「對話方: 」開頭的條目視為病患/系統；取最後一個非對話方條目
        for entry in reversed(history):
            if not str(entry).startswith("對話方:"):
                return str(entry)
        return ""
