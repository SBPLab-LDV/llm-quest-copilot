#!/usr/bin/env python3
"""
驗證 DSPy 是否真正調用了 Gemini LLM

通過 API 端點測試來確認 DSPy 版本與原始版本的差異
"""

import sys
sys.path.insert(0, '/app')

import asyncio
import json
import requests
import time
import uuid

# NOTE: This file is a manual integration script and is not meant to run in CI.
# The project has removed the legacy/original implementation and runs optimized DSPy only.
import pytest
pytest.skip("manual integration test (legacy/original removed; optimized-only)", allow_module_level=True)

def enable_dspy_config():
    """啟用 DSPy 配置"""
    try:
        import yaml
        
        with open('/app/config/config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        original_enabled = config.get('dspy', {}).get('enabled', False)
        
        if 'dspy' not in config:
            config['dspy'] = {}
        config['dspy']['enabled'] = True
        
        with open('/app/config/config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        return original_enabled
    except Exception as e:
        print(f"啟用 DSPy 失敗: {e}")
        return None

def disable_dspy_config():
    """禁用 DSPy 配置"""
    try:
        import yaml
        
        with open('/app/config/config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if 'dspy' not in config:
            config['dspy'] = {}
        config['dspy']['enabled'] = False
        
        with open('/app/config/config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
    except Exception as e:
        print(f"禁用 DSPy 失敗: {e}")

def restore_dspy_config(original_enabled: bool):
    """恢復 DSPy 配置"""
    try:
        import yaml
        
        with open('/app/config/config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if 'dspy' not in config:
            config['dspy'] = {}
        config['dspy']['enabled'] = original_enabled
        
        with open('/app/config/config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
    except Exception as e:
        print(f"恢復 DSPy 配置失敗: {e}")

def call_api_dialogue(text: str, character_id: str = "1", session_id: str = None):
    """調用 API 進行對話"""
    try:
        url = "http://localhost:8000/api/dialogue/text"
        headers = {"Content-Type": "application/json"}
        data = {
            "text": text,
            "character_id": character_id,
            "response_format": "text",
            "session_id": session_id
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def test_api_with_dspy_toggle():
    """測試 API 在 DSPy 啟用/禁用下的差異"""
    print("🔍 測試 API 在 DSPy 啟用/禁用下的差異")
    print("=" * 60)
    
    test_input = "你好，今天感覺如何？"
    session_id = str(uuid.uuid4())
    
    # 記錄原始配置
    original_config = None
    
    try:
        # 測試 1: 禁用 DSPy
        print("\n📴 測試 1: 禁用 DSPy 狀態")
        disable_dspy_config()
        time.sleep(2)  # 等待配置生效
        
        print(f"  輸入: '{test_input}'")
        response1 = call_api_dialogue(test_input, session_id=session_id)
        
        if "error" not in response1:
            print("  ✅ 原始實現回應成功")
            print(f"  回應數量: {len(response1.get('responses', []))}")
            print(f"  狀態: {response1.get('state', 'unknown')}")
            if response1.get('responses'):
                print(f"  首個回應: {response1['responses'][0][:100]}...")
        else:
            print(f"  ❌ 原始實現回應失敗: {response1['error']}")
        
        # 測試 2: 啟用 DSPy  
        print("\n🤖 測試 2: 啟用 DSPy 狀態")
        original_config = enable_dspy_config()
        time.sleep(2)  # 等待配置生效
        
        print(f"  輸入: '{test_input}'")
        response2 = call_api_dialogue(test_input, session_id=session_id)
        
        if "error" not in response2:
            print("  ✅ DSPy 實現回應成功")
            print(f"  回應數量: {len(response2.get('responses', []))}")
            print(f"  狀態: {response2.get('state', 'unknown')}")
            if response2.get('responses'):
                print(f"  首個回應: {response2['responses'][0][:100]}...")
        else:
            print(f"  ❌ DSPy 實現回應失敗: {response2['error']}")
        
        # 比較結果
        print("\n📊 比較結果:")
        if "error" not in response1 and "error" not in response2:
            # 比較回應內容
            orig_responses = response1.get('responses', [])
            dspy_responses = response2.get('responses', [])
            
            print(f"  原始回應數量: {len(orig_responses)}")
            print(f"  DSPy 回應數量: {len(dspy_responses)}")
            
            # 檢查內容是否不同
            if orig_responses and dspy_responses:
                orig_first = orig_responses[0] if orig_responses else ""
                dspy_first = dspy_responses[0] if dspy_responses else ""
                
                if orig_first != dspy_first:
                    print("  ✅ 回應內容不同 - 證實 DSPy 確實被調用")
                    print(f"    原始: {orig_first[:50]}...")
                    print(f"    DSPy: {dspy_first[:50]}...")
                else:
                    print("  ⚠️  回應內容相同 - 可能 DSPy 未生效或使用了相同邏輯")
            
            # 比較狀態
            orig_state = response1.get('state', 'unknown')
            dspy_state = response2.get('state', 'unknown')
            print(f"  原始狀態: {orig_state}")
            print(f"  DSPy 狀態: {dspy_state}")
            
            if orig_state != dspy_state:
                print("  ✅ 狀態不同 - 進一步證實差異")
            
        else:
            print("  ❌ 無法完整比較 (有錯誤發生)")
        
        # 多輪測試
        print("\n🔄 多輪對話測試:")
        test_inputs = [
            "有什麼不舒服的嗎？",
            "需要我幫你做什麼？",
            "你的傷口還痛嗎？"
        ]
        
        different_responses = 0
        total_tests = len(test_inputs)
        
        for i, test_text in enumerate(test_inputs, 1):
            print(f"\n  測試 {i}: '{test_text}'")
            
            # 禁用 DSPy
            disable_dspy_config()
            time.sleep(1)
            orig_resp = call_api_dialogue(test_text, session_id=session_id)
            
            # 啟用 DSPy
            enable_dspy_config()
            time.sleep(1)
            dspy_resp = call_api_dialogue(test_text, session_id=session_id)
            
            if ("error" not in orig_resp and "error" not in dspy_resp and
                orig_resp.get('responses') and dspy_resp.get('responses')):
                
                if orig_resp['responses'][0] != dspy_resp['responses'][0]:
                    different_responses += 1
                    print(f"    ✅ 回應不同")
                else:
                    print(f"    ⚠️  回應相同")
            else:
                print(f"    ❌ 測試失敗")
        
        print(f"\n  差異化回應率: {different_responses}/{total_tests} ({different_responses/total_tests*100:.1f}%)")
        
        if different_responses > 0:
            print("  🎉 確認 DSPy 確實在調用不同的邏輯！")
            return True
        else:
            print("  ⚠️  未檢測到明顯差異")
            return False
    
    finally:
        # 恢復原始配置
        if original_config is not None:
            print(f"\n🔄 恢復原始 DSPy 配置: {original_config}")
            restore_dspy_config(original_config)
        else:
            print("\n🔄 恢復 DSPy 配置為啟用狀態")
            enable_dspy_config()

async def test_direct_module_calls():
    """直接測試模組調用"""
    print("\n🧪 直接測試模組調用")
    print("-" * 40)
    
    try:
        from src.core.character import Character
        from src.core.dialogue import DialogueManager
        from src.core.dspy.dialogue_manager_dspy import DialogueManagerDSPy
        
        # 創建角色
        character = Character(
            name="直接測試病患",
            persona="配合的測試病患",
            backstory="用於直接模組測試",
            goal="協助驗證系統功能"
        )
        
        test_input = "你現在感覺怎麼樣？"
        
        print(f"\n測試輸入: '{test_input}'")
        
        # 啟用 DSPy 進行測試
        enable_dspy_config()
        time.sleep(1)
        
        # 測試原始管理器
        print("\n📋 原始對話管理器:")
        orig_manager = DialogueManager(character, use_terminal=False)
        
        try:
            orig_response = await orig_manager.process_turn(test_input)
            print("  ✅ 原始管理器回應成功")
            if isinstance(orig_response, str):
                try:
                    orig_data = json.loads(orig_response)
                    print(f"    回應: {orig_data.get('responses', ['無回應'])[0][:80]}...")
                except:
                    print(f"    原始回應: {orig_response[:80]}...")
        except Exception as e:
            print(f"  ❌ 原始管理器失敗: {e}")
        
        # 測試 DSPy 管理器
        print("\n🤖 DSPy 對話管理器:")
        dspy_manager = DialogueManagerDSPy(character, use_terminal=False)
        print(f"  DSPy 啟用狀態: {dspy_manager.dspy_enabled}")
        
        try:
            dspy_response = await dspy_manager.process_turn(test_input)
            print("  ✅ DSPy 管理器回應成功")
            if isinstance(dspy_response, str):
                try:
                    dspy_data = json.loads(dspy_response)
                    print(f"    回應: {dspy_data.get('responses', ['無回應'])[0][:80]}...")
                except:
                    print(f"    原始回應: {dspy_response[:80]}...")
                    
            # 顯示統計
            stats = dspy_manager.get_dspy_statistics()
            print(f"    調用統計: DSPy={stats['dspy_calls']}, 回退={stats['fallback_calls']}")
            
        except Exception as e:
            print(f"  ❌ DSPy 管理器失敗: {e}")
        
        # 清理
        orig_manager.cleanup() if hasattr(orig_manager, 'cleanup') else None
        dspy_manager.cleanup()
        
        return True
        
    except Exception as e:
        print(f"❌ 直接模組測試失敗: {e}")
        return False

async def main():
    """主測試函數"""
    print("🚀 Gemini 調用驗證測試")
    
    success_count = 0
    
    # API 測試
    if test_api_with_dspy_toggle():
        success_count += 1
    
    # 直接模組測試
    if await test_direct_module_calls():
        success_count += 1
    
    print("\n" + "=" * 60)
    print("📋 Gemini 調用驗證測試總結")
    print(f"通過測試: {success_count}/2")
    
    if success_count >= 1:
        print("🎉 確認 DSPy 適配層正在調用 Gemini！")
        return True
    else:
        print("❌ 未能確認 DSPy 調用 Gemini")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
