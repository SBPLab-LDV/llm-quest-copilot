#!/usr/bin/env python3
"""
DSPy Gemini 適配器的測試

測試 DSPy 與 Gemini API 的整合是否正常運作。
"""

import sys
import os

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, '/app')

def test_adapter_import():
    """測試適配器導入"""
    print("🧪 測試 DSPy Gemini 適配器導入...")
    
    try:
        from src.llm.dspy_gemini_adapter import DSPyGeminiLM, create_dspy_lm
        print("✅ DSPy Gemini 適配器導入成功")
        return True
        
    except Exception as e:
        print(f"❌ DSPy Gemini 適配器導入失敗: {e}")
        return False

def test_adapter_creation():
    """測試適配器創建"""
    print("🧪 測試 DSPy Gemini 適配器創建...")
    
    try:
        from src.llm.dspy_gemini_adapter import DSPyGeminiLM, create_dspy_lm
        
        # 測試直接創建
        lm1 = DSPyGeminiLM()
        assert lm1 is not None, "DSPyGeminiLM 實例不應為 None"
        
        # 測試從配置創建
        lm2 = create_dspy_lm()
        assert lm2 is not None, "create_dspy_lm 實例不應為 None"
        
        # 測試配置覆寫
        lm3 = create_dspy_lm({"temperature": 0.5})
        assert lm3.temperature == 0.5, "配置覆寫應該生效"
        
        print("✅ DSPy Gemini 適配器創建成功")
        return True
        
    except Exception as e:
        print(f"❌ DSPy Gemini 適配器創建失敗: {e}")
        return False

def test_adapter_interface():
    """測試適配器接口"""
    print("🧪 測試 DSPy Gemini 適配器接口...")
    
    try:
        from src.llm.dspy_gemini_adapter import create_dspy_lm
        import dspy
        
        lm = create_dspy_lm()
        
        # 檢查是否是 dspy.LM 的子類
        assert isinstance(lm, dspy.LM), "DSPyGeminiLM 應該是 dspy.LM 的子類"
        
        # 檢查必要的方法
        assert hasattr(lm, '__call__'), "應該有 __call__ 方法"
        assert hasattr(lm, 'basic_request'), "應該有 basic_request 方法"
        
        # 檢查統計方法
        assert hasattr(lm, 'get_stats'), "應該有 get_stats 方法"
        assert hasattr(lm, 'reset_stats'), "應該有 reset_stats 方法"
        
        # 測試統計信息
        stats = lm.get_stats()
        assert isinstance(stats, dict), "get_stats 應該返回字典"
        assert 'call_count' in stats, "統計應包含 call_count"
        
        print("✅ DSPy Gemini 適配器接口測試通過")
        return True
        
    except Exception as e:
        print(f"❌ DSPy Gemini 適配器接口測試失敗: {e}")
        return False

def test_adapter_basic_call():
    """測試適配器基本調用（簡單測試，不調用真實 API）"""
    print("🧪 測試 DSPy Gemini 適配器基本調用...")
    
    try:
        from src.llm.dspy_gemini_adapter import create_dspy_lm
        
        lm = create_dspy_lm()
        
        # 測試 basic_request 方法存在
        assert callable(lm.basic_request), "basic_request 應該是可調用的"
        
        # 測試 __call__ 方法存在
        assert callable(lm), "實例應該是可調用的"
        
        # 檢查初始統計
        initial_stats = lm.get_stats()
        assert initial_stats['call_count'] == 0, "初始調用計數應為 0"
        
        print("✅ DSPy Gemini 適配器基本調用測試通過")
        return True
        
    except Exception as e:
        print(f"❌ DSPy Gemini 適配器基本調用測試失敗: {e}")
        return False

def run_all_tests():
    """運行所有適配器測試"""
    print("🚀 開始 DSPy Gemini 適配器測試...")
    print("=" * 50)
    
    tests = [
        test_adapter_import,
        test_adapter_creation,
        test_adapter_interface,
        test_adapter_basic_call
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 測試 {test_func.__name__} 出現未預期錯誤: {e}")
        print()
    
    print("=" * 50)
    print(f"📊 測試結果: {passed}/{total} 通過")
    
    if passed == total:
        print("🎉 所有適配器測試都通過了！")
        return True
    else:
        print("⚠️ 部分測試失敗，請檢查上述錯誤訊息")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)