#!/usr/bin/env python3
"""
單一回合退化測試 - 檢查防護系統是否工作
"""

import requests
import json

def test_single_degradation():
    """測試單次退化檢測和防護"""
    print("🔍 單一回合退化防護測試")
    print("=" * 40)
    
    base_url = "http://localhost:8000"
    character_id = "1"
    
    # 發送一個已知會導致退化的請求
    test_input = "還有其他症狀嗎？"
    
    print(f"測試輸入: {test_input}")
    
    try:
        response = requests.post(
            f"{base_url}/api/dialogue/text",
            headers={"Content-Type": "application/json"},
            json={
                "text": test_input,
                "character_id": character_id,
                "response_format": "text"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"✅ 回應狀態: {response.status_code}")
            print(f"📊 回應數量: {len(result.get('responses', []))}")
            print(f"🎭 對話狀態: {result.get('state', 'UNKNOWN')}")
            print(f"🌍 情境: {result.get('dialogue_context', 'UNKNOWN')}")
            print(f"🔧 修復已應用: {result.get('recovery_applied', False)}")
            
            if result.get('recovery_applied'):
                print(f"🎯 原始退化指標: {result.get('original_degradation', [])}")
            
            responses = result.get('responses', [])
            for i, response in enumerate(responses, 1):
                print(f"  [{i}] {response}")
                
            # 檢查是否包含退化模式
            has_degradation = any(
                any(pattern in str(response) for pattern in ["我是Patient", "您需要什麼幫助", "沒有完全理解"])
                for response in responses
            )
            
            print(f"🔍 退化檢測結果: {'🔴 發現退化' if has_degradation else '🟢 無退化'}")
            
        else:
            print(f"❌ HTTP 錯誤: {response.status_code}")
            print(f"錯誤內容: {response.text}")
            
    except Exception as e:
        print(f"❌ 請求失敗: {e}")

if __name__ == "__main__":
    test_single_degradation()