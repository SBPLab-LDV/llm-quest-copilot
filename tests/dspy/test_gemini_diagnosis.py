#!/usr/bin/env python3
"""
診斷 DSPy Gemini 適配器問題

詳細分析 DSPy 初始化、LM 設置和調用過程
"""

import sys
sys.path.insert(0, '/app')

import asyncio
import logging
import json

# NOTE: This file is a manual diagnosis script and is not meant to run in CI.
# The project has removed the non-optimized and legacy implementations.
import pytest
pytest.skip("manual diagnosis script (optimized-only)", allow_module_level=True)

# 設置詳細日誌
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def enable_dspy_config():
    """啟用 DSPy 配置"""
    try:
        import yaml
        
        with open('/app/config/config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if 'dspy' not in config:
            config['dspy'] = {}
        config['dspy']['enabled'] = True
        
        with open('/app/config/config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
        print("✅ DSPy 配置已啟用")
        
    except Exception as e:
        print(f"❌ 啟用 DSPy 失敗: {e}")

def test_dspy_initialization():
    """測試 DSPy 初始化過程"""
    print("🔧 測試 DSPy 初始化...")
    
    try:
        from src.core.dspy.setup import initialize_dspy, is_dspy_initialized, get_dspy_lm
        from src.core.dspy.config import DSPyConfig
        
        # 檢查配置
        print("\n1. 檢查配置:")
        config_manager = DSPyConfig()
        config = config_manager.get_dspy_config()
        
        print(f"  DSPy 啟用: {config_manager.is_dspy_enabled()}")
        print(f"  LM 配置: {config.get('language_model', {})}")
        
        # 嘗試初始化
        print("\n2. 初始化 DSPy:")
        success = initialize_dspy()
        print(f"  初始化結果: {success}")
        
        if success:
            print(f"  DSPy 已初始化: {is_dspy_initialized()}")
            
            # 檢查 LM
            lm = get_dspy_lm()
            print(f"  LM 實例: {type(lm).__name__ if lm else 'None'}")
            
            if lm:
                print(f"  LM 類型: {lm.__class__}")
                print(f"  LM 屬性: {dir(lm)}")
        
        return success
        
    except Exception as e:
        print(f"❌ DSPy 初始化測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gemini_adapter_directly():
    """直接測試 Gemini 適配器"""
    print("\n🤖 直接測試 Gemini 適配器...")
    
    try:
        from src.llm.dspy_gemini_adapter import DSPyGeminiLM
        
        # 創建適配器實例
        print("\n1. 創建適配器實例:")
        adapter = DSPyGeminiLM()
        print("  ✅ 適配器創建成功")
        
        # 測試簡單調用
        print("\n2. 測試簡單調用:")
        test_prompt = "請說：你好"
        print(f"  測試提示: '{test_prompt}'")
        
        try:
            response = adapter(test_prompt)
            print(f"  ✅ 調用成功")
            print(f"  回應: {response[:200]}...")
            return True
            
        except Exception as e:
            print(f"  ❌ 調用失敗: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"❌ 適配器測試失敗: {e}")
        return False

def test_dspy_signature():
    """測試 DSPy Signature"""
    print("\n📝 測試 DSPy Signature...")
    
    try:
        from src.core.dspy.signatures import PatientResponseSignature
        import dspy
        
        # 檢查 signature
        print("\n1. 檢查 PatientResponseSignature:")
        print(f"  輸入欄位: {PatientResponseSignature.model_fields}")
        
        # 嘗試創建 ChainOfThought
        print("\n2. 創建 ChainOfThought 模組:")
        try:
            cot_module = dspy.ChainOfThought(PatientResponseSignature)
            print("  ✅ ChainOfThought 創建成功")
            
            # 測試調用
            print("\n3. 測試 ChainOfThought 調用:")
            try:
                result = cot_module(
                    user_input="你好嗎？",
                    character_name="測試病患",
                    character_persona="友善的病患",
                    character_backstory="住院中",
                    character_goal="康復",
                    character_details={},
                    conversation_history=[]
                )
                
                print("  ✅ ChainOfThought 調用成功")
                print(f"  結果類型: {type(result)}")
                print(f"  結果內容: {result}")
                return True
                
            except Exception as e:
                print(f"  ❌ ChainOfThought 調用失敗: {e}")
                import traceback
                traceback.print_exc()
                return False
                
        except Exception as e:
            print(f"  ❌ ChainOfThought 創建失敗: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Signature 測試失敗: {e}")
        return False

async def test_dialogue_module_step_by_step():
    """逐步測試對話模組"""
    print("\n🗣️ 逐步測試對話模組...")
    
    try:
        from src.core.character import Character
        from src.core.dspy.dialogue_manager_dspy import DialogueManagerDSPy
        
        # 創建角色
        print("\n1. 創建角色:")
        character = Character(
            name="診斷測試病患",
            persona="配合的病患",
            backstory="住院接受治療",
            goal="康復回家"
        )
        print("  ✅ 角色創建成功")
        
        # 創建對話管理器
        print("\n2. 創建對話管理器:")
        manager = DialogueManagerDSPy(character, use_terminal=False)
        print(f"  DSPy 啟用狀態: {manager.dspy_enabled}")
        
        if not manager.dspy_enabled:
            print("  ⚠️ DSPy 未啟用，無法進行進一步測試")
            return False
        
        # 測試對話模組直接調用
        print("\n3. 測試 DSPy 對話模組:")
        try:
            dialogue_module = manager.dialogue_module
            print("  ✅ 對話模組獲取成功")
            
            # 直接調用對話模組
            print("\n4. 直接調用對話模組:")
            prediction = dialogue_module(
                user_input="你今天感覺如何？",
                character_name=character.name,
                character_persona=character.persona,
                character_backstory=character.backstory,
                character_goal=character.goal,
                character_details={},
                conversation_history=[]
            )
            
            print("  ✅ 對話模組調用成功")
            print(f"  預測結果: {prediction}")
            
            if hasattr(prediction, 'responses'):
                print(f"  回應: {prediction.responses}")
            if hasattr(prediction, 'state'):
                print(f"  狀態: {prediction.state}")
            if hasattr(prediction, 'dialogue_context'):
                print(f"  情境: {prediction.dialogue_context}")
                
            return True
            
        except Exception as e:
            print(f"  ❌ 對話模組測試失敗: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"❌ 對話模組測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主診斷函數"""
    print("🔍 DSPy Gemini 診斷測試")
    print("=" * 60)
    
    # 啟用 DSPy
    enable_dspy_config()
    
    success_count = 0
    total_tests = 0
    
    # Test 1: DSPy 初始化
    total_tests += 1
    if test_dspy_initialization():
        success_count += 1
    
    # Test 2: Gemini 適配器
    total_tests += 1
    if test_gemini_adapter_directly():
        success_count += 1
    
    # Test 3: DSPy Signature
    total_tests += 1
    if test_dspy_signature():
        success_count += 1
    
    # Test 4: 對話模組
    total_tests += 1
    if await test_dialogue_module_step_by_step():
        success_count += 1
    
    # 總結
    print("\n" + "=" * 60)
    print("📋 診斷測試總結")
    print(f"通過測試: {success_count}/{total_tests}")
    print(f"成功率: {success_count/total_tests*100:.1f}%")
    
    if success_count >= total_tests * 0.75:
        print("✅ 主要功能正常，可能有小問題需要修復")
        return True
    else:
        print("❌ 發現嚴重問題，需要修復")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n最終診斷結果: {'正常' if result else '異常'}")
