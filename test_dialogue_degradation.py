#!/usr/bin/env python3
"""
對話退化診斷測試
專門用於追蹤和診斷 DSPy 統一對話模組在多輪對話中的退化問題
"""

import requests
import time
from typing import List, Dict, Any, Optional

from tests.dialogue_quality.common import (
    DEFAULT_BASE_URL,
    DEFAULT_CHARACTER_ID,
    FALLBACK_PATTERNS,
    GENERIC_PATTERNS,
    SELF_INTRO_PATTERNS,
    TranscriptRecorder,
    get_character_config,
)


def test_dialogue_degradation(recorder: Optional[TranscriptRecorder] = None) -> List[Dict[str, Any]]:
    """測試對話退化問題"""

    recorder = recorder or TranscriptRecorder("dialogue_degradation")

    recorder.log("🔍 DSPy 對話退化診斷測試")
    recorder.log("=" * 60)

    # 測試配置
    base_url = DEFAULT_BASE_URL
    character_id = DEFAULT_CHARACTER_ID
    character_config = get_character_config(character_id)

    # 標準化測試對話 - 逐步檢查狀態與追問
    test_conversations = [
        {"intent": "rapport_building", "text": "你好，感覺怎麼樣？", "notes": "建立信任、開場"},
        {"intent": "symptom_check", "text": "有沒有覺得發燒或不舒服？", "notes": "確認是否發燒"},
        {"intent": "timeline_probe", "text": "從什麼時候開始的？", "notes": "收集發病時間"},
        {"intent": "additional_symptoms", "text": "還有其他症狀嗎？", "notes": "查找伴隨症狀"},
        {"intent": "care_plan", "text": "那我們安排一些檢查好嗎？", "notes": "提出下一步"},
    ]

    session_id = None
    dialogue_results: List[Dict[str, Any]] = []

    recorder.log(f"📋 將進行 {len(test_conversations)} 輪連續對話測試")
    recorder.log(f"🎯 目標：診斷第4-5輪是否出現退化症狀\n")

    # 執行對話測試
    for round_num, turn in enumerate(test_conversations, 1):
        user_input = turn["text"]
        intent = turn["intent"]
        notes = turn["notes"]

        recorder.log(f"🔵 === 第 {round_num} 輪對話 ===")
        recorder.log(f"  意圖(intent): {intent}")
        recorder.log(f"  說明: {notes}")
        recorder.log(f"護理人員: {user_input}")

        try:
            # 發送請求
            start_time = time.time()
            response = requests.post(
                f"{base_url}/api/dialogue/text",
                headers={"Content-Type": "application/json"},
                json={
                    "text": user_input,
                    "character_id": character_id,
                    "session_id": session_id,
                    "response_format": "text",
                    "character_config": character_config,
                },
                timeout=120
            )
            end_time = time.time()
            response_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()

                # 分析回應質量
                degradation_analysis = analyze_response_quality(round_num, result)

                # 記錄結果
                dialogue_results.append({
                    'round': round_num,
                    'intent': intent,
                    'notes': notes,
                    'user_input': user_input,
                    'response_time': response_time,
                    'session_id': result.get("session_id", session_id),
                    'result': result,
                    'degradation_analysis': degradation_analysis
                })

                # 更新 session_id
                session_id = result.get("session_id", session_id)

                recorder.log(f"✅ 回應時間: {response_time:.2f}s")
                recorder.log(f"📊 實現版本: {result.get('implementation_version', 'UNKNOWN')}")
                recorder.log(f"🆔 Session ID: {session_id or '尚未建立'}")
                recorder.log(f"🎭 對話狀態: {result.get('state', 'UNKNOWN')}")
                recorder.log(f"🌍 情境: {result.get('dialogue_context', 'UNKNOWN')}")
                recorder.log(f"💬 回應數量: {len(result.get('responses', []))}")

                responses = result.get('responses', [])
                for i, text in enumerate(responses, 1):
                    recorder.log(f"    回應[{i}]: {text}")
                if not responses:
                    recorder.log("    ⚠️ 沒有收到任何回應內容")

                fallback_count = degradation_analysis['fallback_count']

                # 退化警告
                if degradation_analysis['is_degraded']:
                    recorder.log(f"🚨 退化警告: {', '.join(degradation_analysis['indicators'])}")
                else:
                    recorder.log("✅ 對話質量正常")

                if fallback_count:
                    recorder.log(f"⚠️ 偵測到 {fallback_count} 次 fallback 回應")

                recorder.log()

            else:
                recorder.log(f"❌ HTTP 錯誤: {response.status_code}")
                recorder.log(f"錯誤內容: {response.text}")
                break
                
        except Exception as e:
            recorder.log(f"❌ 請求失敗: {e}")
            break

    # 生成診斷報告
    recorder.log("📊 === 對話退化診斷報告 ===")
    generate_degradation_report(dialogue_results, recorder=recorder)

    return dialogue_results

def analyze_response_quality(round_num: int, result: Dict[str, Any]) -> Dict[str, Any]:
    """分析回應品質和退化症狀"""
    
    responses = result.get('responses', [])
    state = result.get('state', 'UNKNOWN')
    dialogue_context = result.get('dialogue_context', '')

    indicators = []
    is_degraded = False

    # 檢查1: 自我介紹模式
    has_self_intro = any(
        any(pattern in response for pattern in SELF_INTRO_PATTERNS)
        for response in responses
    )
    if has_self_intro:
        indicators.append("self_introduction")
        is_degraded = True

    # 檢查2: CONFUSED 狀態
    if state == 'CONFUSED':
        indicators.append("confused_state")
        is_degraded = True

    # 檢查3: 通用回應模式
    has_generic = any(
        any(pattern in response for pattern in GENERIC_PATTERNS)
        for response in responses
    )
    if has_generic:
        indicators.append("generic_responses")
        is_degraded = True

    # 檢查3.1: fallback 回應數量
    fallback_hits = [
        response for response in responses
        if any(pattern in response for pattern in FALLBACK_PATTERNS)
    ]
    fallback_count = len(fallback_hits)
    if fallback_count >= 2:
        indicators.append("fallback_overuse")
        is_degraded = True

    # 檢查4: 情境退化（應該保持醫療相關）
    if dialogue_context == "一般問診對話" and round_num > 2:
        indicators.append("context_degradation")
        is_degraded = True

    # 檢查5: 回應數量異常
    if len(responses) == 1 and round_num <= 3:  # 前3輪應該有多個選項
        indicators.append("single_response")
        is_degraded = True

    return {
        'is_degraded': is_degraded,
        'indicators': indicators,
        'has_self_intro': has_self_intro,
        'has_generic': has_generic,
        'fallback_count': fallback_count,
        'fallback_samples': fallback_hits[:3],
        'state': state,
        'context': dialogue_context,
        'response_count': len(responses)
    }

def generate_degradation_report(
    results: List[Dict[str, Any]],
    recorder: Optional[TranscriptRecorder] = None,
) -> None:
    """生成詳細的退化診斷報告"""

    log = recorder.log if recorder else print

    if not results:
        log("❌ 無測試結果可分析")
        return

    log(f"📈 對話輪次: {len(results)}")
    log()

    # 按輪次分析
    degraded_rounds = []
    for result in results:
        round_num = result['round']
        analysis = result['degradation_analysis']

        if analysis['is_degraded']:
            degraded_rounds.append(round_num)
            log(f"🔴 第 {round_num} 輪: 檢測到退化")
            log(f"   指標: {', '.join(analysis['indicators'])}")
            log(f"   狀態: {analysis['state']}")
            log(f"   情境: {analysis['context']}")
            if analysis['fallback_samples']:
                log(f"   Fallback 例句: {analysis['fallback_samples']}")
        else:
            log(f"🟢 第 {round_num} 輪: 品質正常")

    log()

    # 總結分析
    if degraded_rounds:
        log(f"🚨 退化診斷: 在第 {degraded_rounds} 輪出現品質下降")
        if len(degraded_rounds) >= 2 and min(degraded_rounds) >= 4:
            log("💡 診斷: 典型的第4-5輪退化模式 - 符合已知問題")
        elif 1 in degraded_rounds:
            log("💡 診斷: 早期退化 - 可能是系統性問題")
        else:
            log("💡 診斷: 中期退化 - 記憶管理問題")
    else:
        log("✅ 診斷: 未檢測到對話退化 - 系統運行正常")

    # 性能統計
    avg_response_time = sum(r['response_time'] for r in results) / len(results)
    log(f"⏱️  平均回應時間: {avg_response_time:.2f}s")

    # 實現版本統計
    versions = [r['result'].get('implementation_version') for r in results]
    unique_versions = list(set(versions))
    log(f"🔧 使用的實現版本: {unique_versions}")

    log()
    log("📝 建議:")
    if degraded_rounds:
        if any(4 <= r <= 5 for r in degraded_rounds):
            log("   1. 優先修復對話歷史管理機制")
            log("   2. 改善角色狀態持續性")
            log("   3. 優化 DSPy 推理穩定性")
        log("   4. 檢查日誌以了解具體的推理過程變化")
    else:
        log("   系統運行良好，可進行正常使用")

def test_same_input_degradation(recorder: Optional[TranscriptRecorder] = None) -> None:
    """測試相同輸入在不同輪次的行為差異"""

    recorder = recorder or TranscriptRecorder("same_input_probe")

    recorder.log("\n🔁 === 相同輸入重複測試 ===")

    # 使用相同的輸入測試5次
    same_input = "你好，感覺怎麼樣？"
    base_url = DEFAULT_BASE_URL
    character_id = DEFAULT_CHARACTER_ID
    character_config = get_character_config(character_id)
    session_id = None

    results = []

    for i in range(3):
        recorder.log(f"第 {i+1} 次 - 相同輸入: {same_input}")
        
        try:
            response = requests.post(
                f"{base_url}/api/dialogue/text",
                headers={"Content-Type": "application/json"},
                json={
                    "text": same_input,
                    "character_id": character_id,
                    "session_id": session_id,
                    "response_format": "text",
                    "character_config": character_config,
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                session_id = result.get("session_id", session_id)
                
                responses = result.get('responses', [])
                state = result.get('state', 'UNKNOWN')
                
                results.append({
                    'attempt': i+1,
                    'responses': responses,
                    'state': state,
                    'context': result.get('dialogue_context', '')
                })
                
                recorder.log(f"  狀態: {state}")
                recorder.log(f"  session_id: {session_id or '尚未建立'}")
                recorder.log(f"  第1個回應: {responses[0] if responses else 'NONE'}")
                
            else:
                recorder.log(f"  錯誤: HTTP {response.status_code}")
        
        except Exception as e:
            recorder.log(f"  錯誤: {e}")
    
    # 分析差異
    if len(results) > 1:
        recorder.log("\n📊 相同輸入差異分析:")
        for i, result in enumerate(results, 1):
            degraded = any(pattern in str(result['responses']) 
                          for pattern in ["我是Patient", "我可能沒有完全理解"])
            recorder.log(f"  第{i}次: {'🔴 退化' if degraded else '🟢 正常'} - {result['state']}")

if __name__ == "__main__":
    recorder = TranscriptRecorder("dialogue_degradation_suite")
    try:
        # 主要診斷測試
        dialogue_results = test_dialogue_degradation(recorder=recorder)

        # 額外的相同輸入測試
        test_same_input_degradation(recorder=recorder)

        recorder.log("\n✅ 對話退化診斷測試完成")
        recorder.log("💡 查看上方日誌以了解詳細的推理過程和退化指標")
    finally:
        recorder.finalize()
        print(f"📁 Transcript 已保存至 {recorder.log_path}")
