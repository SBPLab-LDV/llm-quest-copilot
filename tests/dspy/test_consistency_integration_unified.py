#!/usr/bin/env python3
"""
整合測試：UnifiedDSPyDialogueModule 與一致性檢查整合
透過 stub/monkeypatch 避免實際 LLM 調用，驗證修正策略與 processing_info 寫入。
"""

import sys
import os

sys.path.insert(0, os.getcwd())
sys.path.insert(0, '/app')

from types import SimpleNamespace

from src.core.dspy.unified_dialogue_module import UnifiedDSPyDialogueModule
import src.core.dspy.dialogue_module as dspy_dialogue_module


def _make_stub_prediction(responses):
    # 模擬 dspy.Prediction 具有必要屬性
    return SimpleNamespace(
        responses=responses,
        state='NORMAL',
        dialogue_context='一般問診對話',
        context_classification='daily_routine_examples',
        confidence=0.9,
        reasoning='stub'
    )


def test_unified_with_consistency_filtering():
    # 避免初始化真實 LM（網路/金鑰依賴），將 initialize_dspy 打成 no-op
    dspy_dialogue_module.initialize_dspy = lambda *_args, **_kwargs: True

    module = UnifiedDSPyDialogueModule(config={"enable_consistency_check": True})

    # monkeypatch 統一生成器，回傳包含自我介紹與通用回應的列表
    stub_responses = [
        "您好，我是王小明",
        "我可能沒有完全理解，能請您換個方式說明嗎",
        "我覺得稍微好一些了，謝謝關心"
    ]
    module.unified_response_generator = lambda **kwargs: _make_stub_prediction(stub_responses)

    history = [
        "護理人員: 你好，今天感覺如何？",
        "病患: 還可以，謝謝關心。",
    ]

    result = module(
        user_input="你現在感覺如何？",
        character_name="測試病患",
        character_persona="友善但有些擔心的病患",
        character_backstory="住院中的老人",
        character_goal="康復出院",
        character_details="",
        conversation_history=history
    )

    # processing_info 應該包含一致性摘要
    assert hasattr(result, 'processing_info')
    info = result.processing_info
    assert 'consistency' in info
    assert 'score' in info['consistency']
    assert 'severity' in info['consistency']

    # 修正策略：應移除自我介紹（high severity）與通用退化回應
    assert all('我是' not in r for r in result.responses)
    assert all('沒有完全理解' not in r for r in result.responses)
    assert any('謝謝關心' in r for r in result.responses)
