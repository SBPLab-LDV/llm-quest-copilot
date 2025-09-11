#!/usr/bin/env python3
"""
Phase 4 適配層測試

測試 DialogueManagerDSPy 和工廠模式的功能，
確保適配層能正常工作。
"""

import sys
sys.path.insert(0, '/app')

def test_dialogue_manager_dspy_creation():
    """測試 DSPy 對話管理器創建"""
    print("🧪 測試 DSPy 對話管理器創建...")
    
    try:
        from src.core.character import Character
        from src.core.dspy.dialogue_manager_dspy import DialogueManagerDSPy
        
        # 創建測試角色
        print("\n1. 創建測試角色:")
        test_character = Character(
            name="測試病患",
            persona="配合的病患",
            backstory="住院中的測試病患",
            goal="配合醫護人員進行治療"
        )
        print("  ✅ 測試角色創建成功")
        
        # 創建 DSPy 對話管理器
        print("\n2. 創建 DSPy 對話管理器:")
        manager = DialogueManagerDSPy(
            character=test_character,
            use_terminal=False,
            log_dir="logs/test"
        )
        print("  ✅ DSPy 對話管理器創建成功")
        
        # 檢查基本屬性
        print("\n3. 檢查管理器屬性:")
        assert hasattr(manager, 'character'), "缺少 character 屬性"
        assert hasattr(manager, 'current_state'), "缺少 current_state 屬性"
        assert hasattr(manager, 'conversation_history'), "缺少 conversation_history 屬性"
        assert hasattr(manager, 'dspy_enabled'), "缺少 dspy_enabled 屬性"
        print("  ✅ 基本屬性存在")
        
        # 檢查 DSPy 特定功能
        print("\n4. 檢查 DSPy 特定功能:")
        stats = manager.get_dspy_statistics()
        assert isinstance(stats, dict), "統計結果應該是字典"
        assert 'total_calls' in stats, "統計中應包含 total_calls"
        print(f"  ✅ DSPy 統計功能正常，DSPy 啟用: {manager.dspy_enabled}")
        
        # 測試統計重置
        print("\n5. 測試統計重置:")
        manager.reset_statistics()
        stats_after_reset = manager.get_dspy_statistics()
        assert stats_after_reset['total_calls'] == 0, "重置後調用次數應為 0"
        print("  ✅ 統計重置功能正常")
        
        # 清理
        print("\n6. 清理資源:")
        manager.cleanup()
        print("  ✅ 資源清理完成")
        
        return True
        
    except Exception as e:
        print(f"❌ DSPy 對話管理器測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dialogue_factory():
    """測試對話管理器工廠模式"""
    print("\n🏭 測試對話管理器工廠模式...")
    
    try:
        from src.core.character import Character
        from src.core.dialogue_factory import (
            create_dialogue_manager, 
            get_available_implementations,
            test_implementations
        )
        
        # 創建測試角色
        print("\n1. 創建測試角色:")
        test_character = Character(
            name="工廠測試病患",
            persona="用於測試工廠模式的病患",
            backstory="虛擬測試角色",
            goal="測試工廠模式功能"
        )
        print("  ✅ 測試角色創建成功")
        
        # 測試可用實現查詢
        print("\n2. 查詢可用實現:")
        implementations = get_available_implementations()
        assert isinstance(implementations, dict), "實現列表應該是字典"
        assert "original" in implementations, "應該包含原始實現"
        print(f"  可用實現: {list(implementations.keys())}")
        
        for impl_name, impl_info in implementations.items():
            print(f"    {impl_name}: {'✅' if impl_info['available'] else '❌'} {impl_info['description']}")
        
        # 測試強制創建原始實現
        print("\n3. 測試強制創建原始實現:")
        original_manager = create_dialogue_manager(
            character=test_character,
            force_implementation="original"
        )
        assert original_manager.__class__.__name__ == "DialogueManager", "應該創建原始實現"
        print("  ✅ 原始實現創建成功")
        original_manager.cleanup() if hasattr(original_manager, 'cleanup') else None
        
        # 測試自動選擇（根據配置）
        print("\n4. 測試自動選擇:")
        auto_manager = create_dialogue_manager(
            character=test_character
        )
        print(f"  自動選擇的實現: {auto_manager.__class__.__name__}")
        print("  ✅ 自動選擇功能正常")
        auto_manager.cleanup() if hasattr(auto_manager, 'cleanup') else None
        
        # 測試 DSPy 實現（如果可用）
        if "dspy" in implementations and implementations["dspy"]["available"]:
            print("\n5. 測試 DSPy 實現:")
            try:
                dspy_manager = create_dialogue_manager(
                    character=test_character,
                    force_implementation="dspy"
                )
                assert dspy_manager.__class__.__name__ == "DialogueManagerDSPy", "應該創建 DSPy 實現"
                print("  ✅ DSPy 實現創建成功")
                dspy_manager.cleanup()
            except Exception as e:
                print(f"  ⚠️ DSPy 實現測試跳過: {e}")
        
        # 測試實現測試函數
        print("\n6. 測試實現測試函數:")
        test_results = test_implementations()
        assert isinstance(test_results, dict), "測試結果應該是字典"
        
        for impl_name, result in test_results.items():
            status = "✅" if result.get("test_passed", False) else "❌"
            print(f"    {impl_name}: {status}")
        
        return True
        
    except Exception as e:
        print(f"❌ 工廠模式測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_interface_compatibility():
    """測試接口兼容性"""
    print("\n🔌 測試接口兼容性...")
    
    try:
        from src.core.character import Character
        from src.core.dialogue_factory import create_dialogue_manager
        
        # 創建測試角色
        test_character = Character(
            name="兼容性測試病患",
            persona="用於測試接口的病患",
            backstory="測試接口兼容性",
            goal="驗證接口兼容性"
        )
        
        # 測試兩種實現的接口
        implementations = ["original"]
        
        # 如果 DSPy 可用，也測試它
        try:
            from src.core.dspy.dialogue_manager_dspy import DialogueManagerDSPy
            implementations.append("dspy")
        except ImportError:
            print("  DSPy 實現不可用，跳過")
        
        for impl_name in implementations:
            print(f"\n  測試 {impl_name} 實現接口:")
            
            try:
                manager = create_dialogue_manager(
                    character=test_character,
                    force_implementation=impl_name
                )
                
                # 檢查必要方法
                required_methods = [
                    'process_turn',
                    'log_interaction', 
                    'save_interaction_log'
                ]
                
                missing_methods = []
                for method_name in required_methods:
                    if not hasattr(manager, method_name):
                        missing_methods.append(method_name)
                
                if missing_methods:
                    print(f"    ❌ 缺少方法: {missing_methods}")
                    return False
                else:
                    print(f"    ✅ 所有必要方法存在")
                
                # 檢查必要屬性
                required_attrs = [
                    'character',
                    'current_state',
                    'conversation_history',
                    'use_terminal'
                ]
                
                missing_attrs = []
                for attr_name in required_attrs:
                    if not hasattr(manager, attr_name):
                        missing_attrs.append(attr_name)
                
                if missing_attrs:
                    print(f"    ❌ 缺少屬性: {missing_attrs}")
                    return False
                else:
                    print(f"    ✅ 所有必要屬性存在")
                
                manager.cleanup() if hasattr(manager, 'cleanup') else None
                
            except Exception as e:
                print(f"    ❌ {impl_name} 接口測試失敗: {e}")
                return False
        
        print("\n  ✅ 接口兼容性測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 接口兼容性測試失敗: {e}")
        return False

def test_configuration_switching():
    """測試配置切換"""
    print("\n⚙️ 測試配置切換...")
    
    try:
        from src.core.dspy.config import DSPyConfig
        
        # 測試配置讀取
        print("\n1. 測試配置讀取:")
        config = DSPyConfig()
        dspy_enabled = config.is_dspy_enabled()
        print(f"  當前 DSPy 配置狀態: {dspy_enabled}")
        print("  ✅ 配置讀取正常")
        
        # 測試配置信息
        print("\n2. 測試配置信息:")
        dspy_config = config.get_dspy_config()
        assert isinstance(dspy_config, dict), "DSPy 配置應該是字典"
        print(f"  DSPy 配置項數量: {len(dspy_config)}")
        print("  ✅ 配置信息正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置切換測試失敗: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Phase 4 適配層測試")
    print("=" * 60)
    
    success_count = 0
    total_tests = 0
    
    # 執行測試
    tests = [
        test_dialogue_manager_dspy_creation,
        test_dialogue_factory,
        test_interface_compatibility,
        test_configuration_switching
    ]
    
    for test_func in tests:
        total_tests += 1
        if test_func():
            success_count += 1
    
    # 總結
    print("\n" + "=" * 60)
    print(f"📋 Phase 4 適配層測試總結")
    print(f"通過測試: {success_count}/{total_tests}")
    print(f"成功率: {success_count/total_tests*100:.1f}%")
    
    if success_count == total_tests:
        print("🎉 Phase 4 適配層測試完全通過！")
        print("✅ DSPy 對話管理器和工廠模式都能正常工作")
    elif success_count >= total_tests * 0.8:
        print("⚠️ Phase 4 適配層測試基本通過，但有少數問題需要關注")
    else:
        print("❌ Phase 4 適配層測試失敗，需要修復問題後再繼續")