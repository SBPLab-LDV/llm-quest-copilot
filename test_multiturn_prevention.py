#!/usr/bin/env python3
"""
多輪對話防護系統測試 - 重點觀察防護系統何時觸發
"""

import requests
import json
import time

def test_multiturn_prevention():
    """測試多輪對話中的防護系統"""
    print("🔍 多輪對話防護系統測試")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    character_id = "1"
    session_id = None
    
    # 測試對話序列
    conversations = [
        "你好，感覺怎麼樣？",
        "有沒有覺得發燒或不舒服？",
        "從什麼時候開始的？",
        "還有其他症狀嗎？",  # 這裡通常會開始退化
        "那我們安排一些檢查好嗎？"
    ]
    
    for round_num, user_input in enumerate(conversations, 1):
        print(f"\n🔵 === 第 {round_num} 輪測試 ===")
        print(f"護理人員: {user_input}")
        
        try:
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
            
            if response.status_code == 200:
                result = response.json()
                session_id = result.get("session_id", session_id)
                
                print(f"⏱️  回應時間: {end_time - start_time:.2f}s")
                print(f"📊 回應數量: {len(result.get('responses', []))}")
                print(f"🎭 對話狀態: {result.get('state', 'UNKNOWN')}")
                print(f"🌍 情境: {result.get('dialogue_context', 'UNKNOWN')}")
                
                # 關鍵檢查：防護系統是否被觸發
                if result.get('recovery_applied'):
                    print(f"🛡️  防護系統已觸發!")
                    print(f"🔧 修復已應用: {result.get('recovery_applied')}")
                    print(f"🎯 原始退化指標: {result.get('original_degradation', [])}")
                else:
                    print(f"ℹ️  防護系統未觸發 (正常狀況)")
                
                responses = result.get('responses', [])
                
                # 顯示前2個回應
                for i, response in enumerate(responses[:2], 1):
                    print(f"  [{i}] {response}")
                if len(responses) > 2:
                    print(f"  ... 還有 {len(responses) - 2} 個回應")
                
                # 檢查退化模式
                has_degradation = any(
                    any(pattern in str(response) for pattern in ["我是Patient", "您需要什麼幫助", "沒有完全理解"])
                    for response in responses
                )
                
                if has_degradation and not result.get('recovery_applied'):
                    print(f"🚨 警告: 檢測到退化但防護系統未觸發!")
                elif has_degradation and result.get('recovery_applied'):
                    print(f"✅ 檢測到退化，防護系統成功介入")
                else:
                    print(f"✅ 品質正常")
                    
            else:
                print(f"❌ HTTP 錯誤: {response.status_code}")
                break
                
        except Exception as e:
            print(f"❌ 請求失敗: {e}")
            break
    
    print(f"\n📝 多輪對話防護系統測試完成")

if __name__ == "__main__":
    test_multiturn_prevention()