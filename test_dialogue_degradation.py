#!/usr/bin/env python3
"""
對話退化診斷測試
專門用於追蹤和診斷 DSPy 統一對話模組在多輪對話中的退化問題
"""

import requests
import json
import time
from typing import List, Dict, Any
import logging

# 設置詳細日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_dialogue_degradation():
    """測試對話退化問題"""
    
    print("🔍 DSPy 對話退化診斷測試")
    print("=" * 60)
    
    # 測試配置
    base_url = "http://localhost:8000"
    character_id = "1"
    
    # 標準化測試對話 - 相同的問題重複問5次
    test_conversations = [
        "你好，感覺怎麼樣？",
        "有沒有覺得發燒或不舒服？", 
        "從什麼時候開始的？",
        "還有其他症狀嗎？",
        "那我們安排一些檢查好嗎？"
    ]
    
    session_id = None
    dialogue_results = []
    
    print(f"📋 將進行 {len(test_conversations)} 輪連續對話測試")
    print(f"🎯 目標：診斷第4-5輪是否出現退化症狀\n")
    
    # 執行對話測試
    for round_num, user_input in enumerate(test_conversations, 1):
        print(f"🔵 === 第 {round_num} 輪對話 === ")
        print(f"護理人員: {user_input}")
        
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
                    "response_format": "text"
                },
                timeout=30
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
                    'user_input': user_input,
                    'response_time': response_time,
                    'result': result,
                    'degradation_analysis': degradation_analysis
                })
                
                # 更新 session_id
                session_id = result.get("session_id", session_id)
                
                print(f"✅ 回應時間: {response_time:.2f}s")
                print(f"📊 實現版本: {result.get('implementation_version', 'UNKNOWN')}")
                print(f"🎭 對話狀態: {result.get('state', 'UNKNOWN')}")
                print(f"🌍 情境: {result.get('dialogue_context', 'UNKNOWN')}")
                print(f"💬 回應數量: {len(result.get('responses', []))}")
                
                # 顯示前2個回應樣本
                responses = result.get('responses', [])
                for i, response in enumerate(responses[:2], 1):
                    print(f"  [{i}] {response}")
                if len(responses) > 2:
                    print(f"  ... 還有 {len(responses) - 2} 個回應")
                
                # 退化警告
                if degradation_analysis['is_degraded']:
                    print(f"🚨 退化警告: {', '.join(degradation_analysis['indicators'])}")
                else:
                    print(f"✅ 對話質量正常")
                
                print()
                
            else:
                print(f"❌ HTTP 錯誤: {response.status_code}")
                print(f"錯誤內容: {response.text}")
                break
                
        except Exception as e:
            print(f"❌ 請求失敗: {e}")
            break
    
    # 生成診斷報告
    print("📊 === 對話退化診斷報告 ===")
    generate_degradation_report(dialogue_results)
    
    return dialogue_results

def analyze_response_quality(round_num: int, result: Dict[str, Any]) -> Dict[str, Any]:
    """分析回應品質和退化症狀"""
    
    responses = result.get('responses', [])
    state = result.get('state', 'UNKNOWN')
    dialogue_context = result.get('dialogue_context', '')
    
    indicators = []
    is_degraded = False
    
    # 檢查1: 自我介紹模式
    self_intro_patterns = ["我是Patient", "您好，我是", "我是病患"]
    has_self_intro = any(
        any(pattern in response for pattern in self_intro_patterns)
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
    generic_patterns = ["我可能沒有完全理解", "能請您換個方式說明", "您需要什麼幫助嗎"]
    has_generic = any(
        any(pattern in response for pattern in generic_patterns)
        for response in responses
    )
    if has_generic:
        indicators.append("generic_responses")
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
        'state': state,
        'context': dialogue_context,
        'response_count': len(responses)
    }

def generate_degradation_report(results: List[Dict[str, Any]]):
    """生成詳細的退化診斷報告"""
    
    if not results:
        print("❌ 無測試結果可分析")
        return
    
    print(f"📈 對話輪次: {len(results)}")
    print()
    
    # 按輪次分析
    degraded_rounds = []
    for result in results:
        round_num = result['round']
        analysis = result['degradation_analysis']
        
        if analysis['is_degraded']:
            degraded_rounds.append(round_num)
            print(f"🔴 第 {round_num} 輪: 檢測到退化")
            print(f"   指標: {', '.join(analysis['indicators'])}")
            print(f"   狀態: {analysis['state']}")
            print(f"   情境: {analysis['context']}")
        else:
            print(f"🟢 第 {round_num} 輪: 品質正常")
    
    print()
    
    # 總結分析
    if degraded_rounds:
        print(f"🚨 退化診斷: 在第 {degraded_rounds} 輪出現品質下降")
        if len(degraded_rounds) >= 2 and min(degraded_rounds) >= 4:
            print("💡 診斷: 典型的第4-5輪退化模式 - 符合已知問題")
        elif 1 in degraded_rounds:
            print("💡 診斷: 早期退化 - 可能是系統性問題")
        else:
            print("💡 診斷: 中期退化 - 記憶管理問題")
    else:
        print("✅ 診斷: 未檢測到對話退化 - 系統運行正常")
    
    # 性能統計
    avg_response_time = sum(r['response_time'] for r in results) / len(results)
    print(f"⏱️  平均回應時間: {avg_response_time:.2f}s")
    
    # 實現版本統計
    versions = [r['result'].get('implementation_version') for r in results]
    unique_versions = list(set(versions))
    print(f"🔧 使用的實現版本: {unique_versions}")
    
    print()
    print("📝 建議:")
    if degraded_rounds:
        if any(4 <= r <= 5 for r in degraded_rounds):
            print("   1. 優先修復對話歷史管理機制")
            print("   2. 改善角色狀態持續性")
            print("   3. 優化 DSPy 推理穩定性")
        print("   4. 檢查日誌以了解具體的推理過程變化")
    else:
        print("   系統運行良好，可進行正常使用")

def test_same_input_degradation():
    """測試相同輸入在不同輪次的行為差異"""
    
    print("\n🔁 === 相同輸入重複測試 ===")
    
    # 使用相同的輸入測試5次
    same_input = "你好，感覺怎麼樣？"
    base_url = "http://localhost:8000"
    character_id = "1"
    session_id = None
    
    results = []
    
    for i in range(5):
        print(f"第 {i+1} 次 - 相同輸入: {same_input}")
        
        try:
            response = requests.post(
                f"{base_url}/api/dialogue/text",
                headers={"Content-Type": "application/json"},
                json={
                    "text": same_input,
                    "character_id": character_id,
                    "session_id": session_id,
                    "response_format": "text"
                },
                timeout=30
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
                
                print(f"  狀態: {state}")
                print(f"  第1個回應: {responses[0] if responses else 'NONE'}")
                
            else:
                print(f"  錯誤: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"  錯誤: {e}")
    
    # 分析差異
    if len(results) > 1:
        print("\n📊 相同輸入差異分析:")
        for i, result in enumerate(results, 1):
            degraded = any(pattern in str(result['responses']) 
                          for pattern in ["我是Patient", "我可能沒有完全理解"])
            print(f"  第{i}次: {'🔴 退化' if degraded else '🟢 正常'} - {result['state']}")

if __name__ == "__main__":
    # 主要診斷測試
    dialogue_results = test_dialogue_degradation()
    
    # 額外的相同輸入測試
    test_same_input_degradation()
    
    print("\n✅ 對話退化診斷測試完成")
    print("💡 查看上方日誌以了解詳細的推理過程和退化指標")