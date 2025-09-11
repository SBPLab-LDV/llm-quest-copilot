#!/usr/bin/env python3
"""
DSPy 設置和初始化的測試

測試 DSPy 初始化、配置和生命週期管理是否正常運作。
"""

import sys
import os

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, '/app')

def test_setup_import():
    """測試設置模組導入"""
    print("🧪 測試 DSPy 設置模組導入...")
    
    try:
        from src.core.dspy.setup import (
            DSPyManager, get_dspy_manager, initialize_dspy,
            is_dspy_initialized, cleanup_dspy
        )
        print("✅ DSPy 設置模組導入成功")
        return True
        
    except Exception as e:
        print(f"❌ DSPy 設置模組導入失敗: {e}")
        return False

def test_manager_creation():
    """測試管理器創建"""
    print("🧪 測試 DSPy 管理器創建...")
    
    try:
        from src.core.dspy.setup import DSPyManager, get_dspy_manager
        
        # 測試直接創建
        manager1 = DSPyManager()
        assert manager1 is not None, "DSPyManager 實例不應為 None"
        assert not manager1.is_initialized(), "新建管理器應該未初始化"
        
        # 測試全局管理器
        manager2 = get_dspy_manager()
        assert manager2 is not None, "全局管理器不應為 None"
        
        # 測試單例模式
        manager3 = get_dspy_manager()
        assert manager2 is manager3, "全局管理器應該是單例"
        
        print("✅ DSPy 管理器創建成功")
        return True
        
    except Exception as e:
        print(f"❌ DSPy 管理器創建失敗: {e}")
        return False

def test_initialization():
    """測試初始化功能"""
    print("🧪 測試 DSPy 初始化...")
    
    try:
        from src.core.dspy.setup import (
            initialize_dspy, is_dspy_initialized, 
            get_dspy_lm, cleanup_dspy
        )
        
        # 確保初始狀態乾淨
        cleanup_dspy()
        assert not is_dspy_initialized(), "初始狀態應該未初始化"
        
        # 測試初始化
        success = initialize_dspy()
        assert success, "DSPy 初始化應該成功"
        assert is_dspy_initialized(), "初始化後狀態應該為已初始化"
        
        # 測試獲取 LM
        lm = get_dspy_lm()
        assert lm is not None, "應該能獲取到 LM 實例"
        
        # 測試重複初始化
        success2 = initialize_dspy()
        assert success2, "重複初始化應該成功"
        
        # 測試清理
        cleanup_dspy()
        assert not is_dspy_initialized(), "清理後應該未初始化"
        
        print("✅ DSPy 初始化測試成功")
        return True
        
    except Exception as e:
        print(f"❌ DSPy 初始化測試失敗: {e}")
        # 確保清理
        try:
            from src.core.dspy.setup import cleanup_dspy
            cleanup_dspy()
        except:
            pass
        return False

def test_context_manager():
    """測試上下文管理器"""
    print("🧪 測試 DSPy 上下文管理器...")
    
    try:
        from src.core.dspy.setup import (
            with_dspy, is_dspy_initialized, cleanup_dspy
        )
        
        # 確保初始狀態乾淨
        cleanup_dspy()
        assert not is_dspy_initialized(), "初始狀態應該未初始化"
        
        # 測試上下文管理器
        with with_dspy() as manager:
            assert manager is not None, "管理器不應為 None"
            assert is_dspy_initialized(), "上下文中應該已初始化"
            
            lm = manager.get_lm()
            assert lm is not None, "應該能獲取到 LM 實例"
        
        # 測試退出後自動清理
        assert not is_dspy_initialized(), "退出上下文後應該自動清理"
        
        print("✅ DSPy 上下文管理器測試成功")
        return True
        
    except Exception as e:
        print(f"❌ DSPy 上下文管理器測試失敗: {e}")
        # 確保清理
        try:
            from src.core.dspy.setup import cleanup_dspy
            cleanup_dspy()
        except:
            pass
        return False

def test_stats():
    """測試統計信息"""
    print("🧪 測試 DSPy 統計信息...")
    
    try:
        from src.core.dspy.setup import (
            initialize_dspy, get_dspy_stats, cleanup_dspy
        )
        
        # 確保初始狀態乾淨
        cleanup_dspy()
        
        # 測試未初始化時的統計
        stats1 = get_dspy_stats()
        assert isinstance(stats1, dict), "統計信息應該是字典"
        assert not stats1['initialized'], "未初始化時應該為 False"
        
        # 初始化後的統計
        initialize_dspy()
        stats2 = get_dspy_stats()
        assert stats2['initialized'], "初始化後應該為 True"
        assert stats2['lm_stats'] is not None, "應該有 LM 統計信息"
        
        cleanup_dspy()
        print("✅ DSPy 統計信息測試成功")
        return True
        
    except Exception as e:
        print(f"❌ DSPy 統計信息測試失敗: {e}")
        # 確保清理
        try:
            from src.core.dspy.setup import cleanup_dspy
            cleanup_dspy()
        except:
            pass
        return False

def run_all_tests():
    """運行所有設置測試"""
    print("🚀 開始 DSPy 設置測試...")
    print("=" * 50)
    
    tests = [
        test_setup_import,
        test_manager_creation,
        test_initialization,
        test_context_manager,
        test_stats
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
        print("🎉 所有設置測試都通過了！")
        return True
    else:
        print("⚠️ 部分測試失敗，請檢查上述錯誤訊息")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)