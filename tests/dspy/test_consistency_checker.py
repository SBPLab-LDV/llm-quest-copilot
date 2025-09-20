#!/usr/bin/env python3
"""
單元測試：對話一致性檢查器（規則版）
不依賴 LLM，可離線 determinisitc 驗證。
"""

import sys
import os

# 允許在容器與本機雙環境運行
sys.path.insert(0, os.getcwd())
sys.path.insert(0, '/app')

from src.core.dspy.consistency_checker import DialogueConsistencyChecker


def test_bootstrap_noop():
    checker = DialogueConsistencyChecker()
    result = checker.check_consistency(new_responses=["好的"], conversation_history=[], character_context=None)
    assert hasattr(result, 'score')
    assert 0.0 <= result.score <= 1.0
    assert result.has_contradictions in (True, False)


def test_fever_state_flip():
    checker = DialogueConsistencyChecker()
    history = ["護理人員: 你有發燒嗎？", "病患: 我沒有發燒"]
    new_responses = ["昨晚開始發燒，頭有點暈"]
    result = checker.check_consistency(new_responses=new_responses, conversation_history=history, character_context=None)
    assert result.has_contradictions is True
    assert any(c.type == 'fever_state_flip' for c in result.contradictions)


def test_self_introduction_detection():
    checker = DialogueConsistencyChecker()
    history = []
    new_responses = ["您好，我是王小明，請多指教"]
    result = checker.check_consistency(new_responses=new_responses, conversation_history=history, character_context=None)
    assert result.has_contradictions is True
    assert any(c.type == 'self_introduction' for c in result.contradictions)
    assert result.severity == 'high'


def test_generic_response_detection():
    checker = DialogueConsistencyChecker()
    history = []
    new_responses = ["我可能沒有完全理解，可否換個方式說明"]
    result = checker.check_consistency(new_responses=new_responses, conversation_history=history, character_context=None)
    assert result.has_contradictions is True
    assert any(c.type == 'generic_response' for c in result.contradictions)


def test_timeline_inconsistency_detection():
    checker = DialogueConsistencyChecker()
    history = ["病患: 今天早上開始覺得有點熱"]
    new_responses = ["我昨晚開始發燒，半夜有點不舒服"]
    result = checker.check_consistency(new_responses=new_responses, conversation_history=history, character_context=None)
    assert any(c.type == 'timeline_inconsistency' for c in result.contradictions)

