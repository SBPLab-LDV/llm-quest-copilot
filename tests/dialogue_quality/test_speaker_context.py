"""
Speaker/Context 適切性測試

驗證病患回應是否適合該對話方角色與情境。
這是 inferred_speaker_role 功能的品質驗證測試。

使用方式：
    pytest tests/dialogue_quality/test_speaker_context.py -v
    python tests/dialogue_quality/test_speaker_context.py  # 獨立執行
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests

# 確保可以 import src 模組
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.dialogue_quality.common import (
    DEFAULT_BASE_URL,
    TranscriptRecorder,
)

# 測試用 API URL（可透過環境變數覆蓋）
API_BASE_URL = os.environ.get("DIALOGUE_API_URL", "http://localhost:18000")


# =============================================================================
# 測試案例定義
# =============================================================================

SPEAKER_CONTEXT_TEST_CASES: List[Dict[str, Any]] = [
    {
        "name": "物理治療師",
        "expected_speaker": "物理治療師",
        "acceptable_speakers": ["物理治療師"],  # 嚴格匹配
        "expected_context": "物理治療",
        "question": "嘴巴現在張得怎麼樣？有沒有比較打開？",
        "expected_keywords": ["張", "緊", "鬆", "比較", "練習", "開"],
        "forbidden_keywords": ["吃飯", "藥物", "血壓", "檢查報告"],
    },
    {
        "name": "營養師",
        "expected_speaker": "營養師",
        "acceptable_speakers": ["營養師", "護理師"],  # 營養問題護理師也會問
        "expected_context": "營養諮詢",
        "question": "營養補充品有在吃嗎？",
        "expected_keywords": ["吃", "配方", "食慾", "營養", "補充"],
        "forbidden_keywords": ["張嘴", "復健動作", "傷口"],
    },
    {
        "name": "護理師",
        "expected_speaker": "護理師",
        "acceptable_speakers": ["護理師"],
        "expected_context": "生命徵象",
        "question": "量一下血壓和體溫",
        "expected_keywords": ["好", "可以", "沒問題", "量"],
        "forbidden_keywords": ["治療方案決定", "復健計畫"],
    },
    {
        "name": "醫師",
        "expected_speaker": "醫師",
        "acceptable_speakers": ["醫師", "護理師"],  # 護理師也可能轉達檢查結果
        "expected_context": "醫師查房",
        "question": "腫瘤指數有下降，這是好消息",
        "expected_keywords": ["好", "謝謝", "繼續", "治療", "希望"],
        "forbidden_keywords": ["換藥程序", "日常瑣事"],
    },
    {
        "name": "照顧者",
        "expected_speaker": "照顧者",
        "acceptable_speakers": ["照顧者"],
        "expected_context": "照顧者互動",
        "question": "爸，你今天有沒有比較好一點？",
        "expected_keywords": ["好", "累", "休息", "想", "精神"],
        "forbidden_keywords": ["診斷", "檢查報告", "治療方案"],
    },
]


# =============================================================================
# API 輔助函數
# =============================================================================


def call_dialogue_api(
    text: str, character_id: str = "1", base_url: str = None
) -> Dict[str, Any]:
    """呼叫對話 API

    Args:
        text: 對話方問題
        character_id: 角色 ID
        base_url: API 基底 URL

    Returns:
        API 回應
    """
    url = f"{base_url or API_BASE_URL}/api/dialogue/text"
    try:
        response = requests.post(
            url,
            json={"text": text, "character_id": character_id},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# =============================================================================
# 評估函數
# =============================================================================


def evaluate_response_appropriateness(
    responses: List[str],
    expected_keywords: List[str],
    forbidden_keywords: List[str],
) -> Dict[str, Any]:
    """評估回應的適切性

    Args:
        responses: 回應列表
        expected_keywords: 預期關鍵詞
        forbidden_keywords: 禁止關鍵詞

    Returns:
        評估結果
    """
    responses_text = " ".join(responses)

    # 計算正向匹配
    expected_hits = [kw for kw in expected_keywords if kw in responses_text]

    # 計算負向匹配
    forbidden_hits = [kw for kw in forbidden_keywords if kw in responses_text]

    # 計算分數
    if expected_keywords:
        expected_score = len(expected_hits) / len(expected_keywords)
    else:
        expected_score = 1.0

    penalty = len(forbidden_hits) * 0.2
    overall_score = max(0, expected_score - penalty)

    return {
        "expected_hits": expected_hits,
        "expected_count": f"{len(expected_hits)}/{len(expected_keywords)}",
        "forbidden_hits": forbidden_hits,
        "forbidden_count": len(forbidden_hits),
        "overall_score": round(overall_score, 2),
        "pass": overall_score >= 0.4 and len(forbidden_hits) == 0,
    }


# =============================================================================
# pytest 測試
# =============================================================================


@pytest.fixture(scope="module")
def api_available():
    """檢查 API 是否可用"""
    try:
        # 嘗試發送一個簡單的對話請求來確認 API 可用
        response = requests.post(
            f"{API_BASE_URL}/api/dialogue/text",
            json={"text": "你好", "character_id": "1"},
            timeout=30,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@pytest.mark.parametrize("case", SPEAKER_CONTEXT_TEST_CASES, ids=lambda c: c["name"])
def test_speaker_inference(case: Dict[str, Any], api_available):
    """測試對話方角色推理是否正確

    注意：inferred_speaker_role 已棄用，此測試現在只驗證 API 回應正常
    角色推理已整合到 context_classification 中
    """
    if not api_available:
        pytest.skip("API 不可用")

    response = call_dialogue_api(case["question"])

    if "error" in response:
        pytest.fail(f"API 錯誤: {response['error']}")

    # inferred_speaker_role 已棄用，現在總是回傳 None
    # 改為驗證 dialogue_context 有正常回傳
    dialogue_context = response.get("dialogue_context", "")
    assert dialogue_context, "dialogue_context 應該有值"


@pytest.mark.parametrize("case", SPEAKER_CONTEXT_TEST_CASES, ids=lambda c: c["name"])
def test_response_appropriateness(case: Dict[str, Any], api_available):
    """測試回應內容是否適合該角色"""
    if not api_available:
        pytest.skip("API 不可用")

    response = call_dialogue_api(case["question"])

    if "error" in response:
        pytest.fail(f"API 錯誤: {response['error']}")

    responses = response.get("responses", [])

    # 評估適切性
    eval_result = evaluate_response_appropriateness(
        responses=responses,
        expected_keywords=case["expected_keywords"],
        forbidden_keywords=case["forbidden_keywords"],
    )

    # 檢查禁止詞彙
    assert len(eval_result["forbidden_hits"]) == 0, (
        f"出現禁止詞彙: {eval_result['forbidden_hits']}"
    )

    # 檢查整體分數
    assert eval_result["overall_score"] >= 0.2, (
        f"適切性分數過低: {eval_result['overall_score']}"
    )


# =============================================================================
# LLM-as-Judge 測試
# =============================================================================


@pytest.mark.slow
def test_with_llm_judge(api_available):
    """使用 LLM-as-Judge 進行深度評估

    這個測試較慢，需要呼叫 LLM，使用 -m slow 執行：
        pytest tests/dialogue_quality/test_speaker_context.py -m slow
    """
    if not api_available:
        pytest.skip("API 不可用")

    # 初始化 DSPy（設定全域 LM）
    from src.core.dspy.setup import initialize_dspy
    initialize_dspy()

    from src.core.dspy.llm_judge import ResponseQualityJudge

    judge = ResponseQualityJudge()

    test_cases = []
    for case in SPEAKER_CONTEXT_TEST_CASES:
        response = call_dialogue_api(case["question"])
        if "error" not in response:
            test_cases.append({
                "question": case["question"],
                "responses": response.get("responses", []),
                "inferred_speaker": response.get("inferred_speaker_role", ""),
                "dialogue_context": response.get("dialogue_context", ""),
                "expected_speaker": case["expected_speaker"],
            })

    if not test_cases:
        pytest.skip("無法取得測試資料")

    # 使用真正的 LLM 評估（語意理解）
    results = judge.batch_evaluate(test_cases, use_llm=True)

    # 輸出詳細結果供調試
    print(f"\nLLM Judge 結果: 通過率 {results['pass_rate']:.1%}, 平均分 {results['average_score']}")

    # LLM 評估使用 1-5 分制，3.5 為及格門檻
    assert results["average_score"] >= 3.5, (
        f"平均分過低: {results['average_score']}"
    )


# =============================================================================
# 獨立執行模式
# =============================================================================


def run_manual_evaluation():
    """手動執行評估（獨立模式）"""
    print("=" * 60)
    print("Speaker/Context 適切性評估")
    print("=" * 60)

    results = []

    for case in SPEAKER_CONTEXT_TEST_CASES:
        print(f"\n--- {case['name']} ---")
        print(f"問題: {case['question']}")

        response = call_dialogue_api(case["question"])

        if "error" in response:
            print(f"錯誤: {response['error']}")
            continue

        # 檢查情境（inferred_speaker_role 已棄用）
        dialogue_context = response.get("dialogue_context", "N/A")
        context_ok = case["expected_context"] in dialogue_context if dialogue_context != "N/A" else False
        print(f"對話情境: {dialogue_context} {'✅' if context_ok else '⚠️'}")
        print(f"（注意：inferred_speaker_role 已棄用，改用 context_classification）")

        # 顯示回應
        responses = response.get("responses", [])
        print("回應選項:")
        for i, r in enumerate(responses, 1):
            print(f"  {i}. {r}")

        # 評估適切性
        eval_result = evaluate_response_appropriateness(
            responses=responses,
            expected_keywords=case["expected_keywords"],
            forbidden_keywords=case["forbidden_keywords"],
        )

        print(f"預期詞命中: {eval_result['expected_count']}")
        if eval_result["forbidden_hits"]:
            print(f"禁止詞出現: {eval_result['forbidden_hits']} ❌")
        print(f"適切性分數: {eval_result['overall_score']}")
        print(f"通過: {'✅' if eval_result['pass'] else '❌'}")

        results.append({
            "name": case["name"],
            "context_ok": context_ok,
            "eval_pass": eval_result["pass"],
            "score": eval_result["overall_score"],
        })

    # 統計結果
    print("\n" + "=" * 60)
    print("統計結果")
    print("=" * 60)

    context_correct = sum(1 for r in results if r["context_ok"])
    eval_passed = sum(1 for r in results if r["eval_pass"])
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0

    print(f"情境判斷正確: {context_correct}/{len(results)}")
    print(f"適切性通過: {eval_passed}/{len(results)}")
    print(f"平均分數: {avg_score:.2f}")

    return results


if __name__ == "__main__":
    run_manual_evaluation()
