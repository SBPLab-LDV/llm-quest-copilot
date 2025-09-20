#!/usr/bin/env python3
"""
簡化的 DSPy 對話模組測試
專注於模組創建和基本功能，避免實際的 LM 調用
"""

import sys
sys.path.insert(0, '/app')

def test_dialogue_module_creation():
    """測試對話模組創建和初始化"""
    print("🧪 測試 DSPy 對話模組創建...")
    
    try:
        from src.core.dspy.dialogue_module import DSPyDialogueModule
        
        # 測試模組創建
        print("\n1. 創建對話模組:")
        module = DSPyDialogueModule()
        print("  ✅ 模組創建成功")
        
        # 檢查模組組件
        print("\n2. 檢查模組組件:")
        assert hasattr(module, 'context_classifier'), "缺少 context_classifier"
        assert hasattr(module, 'response_generator'), "缺少 response_generator"  
        assert hasattr(module, 'example_selector'), "缺少 example_selector"
        assert hasattr(module, 'stats'), "缺少 stats"
        print("  ✅ 所有組件存在")
        
        # 檢查統計功能
        print("\n3. 檢查統計功能:")
        stats = module.get_statistics()
        assert isinstance(stats, dict), "統計結果應該是字典"
        assert 'total_calls' in stats, "統計中應包含 total_calls"
        assert 'success_rate' in stats, "統計中應包含 success_rate"
        print(f"  ✅ 統計功能正常，初始調用次數: {stats['total_calls']}")
        
        # 檢查輔助方法
        print("\n4. 檢查輔助方法:")
        contexts = module._get_available_contexts()
        assert isinstance(contexts, str), "情境列表應該是字符串"
        assert len(contexts) > 0, "情境列表不應為空"
        print(f"  ✅ 輔助方法正常，找到情境: {contexts.count('_examples')} 個")
        
        # 測試回應格式處理
        print("\n5. 測試回應處理:")
        test_responses = [
            "這是一個簡單回應",
            ["回應1", "回應2", "回應3"],
            '["JSON回應1", "JSON回應2"]',
            "多行\n回應\n測試"
        ]
        
        for i, test_resp in enumerate(test_responses, 1):
            processed = module._process_responses(test_resp)
            assert isinstance(processed, list), f"處理後應該是列表，但得到 {type(processed)}"
            assert len(processed) > 0, "處理後不應為空"
            print(f"    測試 {i}: {type(test_resp).__name__} -> {len(processed)} 個回應")
        
        print("  ✅ 回應處理功能正常")
        
        # 測試錯誤回應創建
        print("\n6. 測試錯誤處理:")
        error_response = module._create_error_response("測試輸入", "測試錯誤")
        assert hasattr(error_response, 'responses'), "錯誤回應應包含 responses"
        assert hasattr(error_response, 'state'), "錯誤回應應包含 state"
        assert error_response.state == "CONFUSED", f"錯誤狀態應為 CONFUSED，但得到 {error_response.state}"
        print("  ✅ 錯誤處理功能正常")
        
        # 測試統計重置
        print("\n7. 測試統計重置:")
        module.reset_statistics()
        stats_after_reset = module.get_statistics()
        assert stats_after_reset['total_calls'] == 0, "重置後調用次數應為 0"
        print("  ✅ 統計重置功能正常")
        
        # 清理資源
        print("\n8. 清理資源:")
        module.cleanup()
        print("  ✅ 資源清理完成")
        
        print("\n✅ DSPy 對話模組基本功能測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 對話模組測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dialogue_module_components():
    """測試對話模組各組件"""
    print("\n🔧 測試對話模組組件...")
    
    try:
        from src.core.dspy.dialogue_module import DSPyDialogueModule
        
        module = DSPyDialogueModule()
        
        # 測試範例選擇器
        print("\n1. 測試範例選擇器:")
        examples = module._select_examples("測試查詢", "daily_routine_examples")
        print(f"  選擇範例數量: {len(examples)}")
        
        # 測試統計更新
        print("\n2. 測試統計更新:")
        initial_stats = module.get_statistics()
        module._update_stats("test_context", "NORMAL")
        updated_stats = module.get_statistics()
        
        assert 'test_context' in updated_stats['context_predictions'], "統計應包含新情境"
        assert 'NORMAL' in updated_stats['state_transitions'], "統計應包含新狀態"
        print("  ✅ 統計更新正常")
        
        module.cleanup()
        print("\n✅ 組件測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 組件測試失敗: {e}")
        return False

if __name__ == "__main__":
    success1 = test_dialogue_module_creation()
    success2 = test_dialogue_module_components()
    
    if success1 and success2:
        print("\n🎉 所有測試通過！")
    else:
        print("\n⚠️  部分測試失敗")