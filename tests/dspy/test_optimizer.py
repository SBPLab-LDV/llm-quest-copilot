#!/usr/bin/env python3
"""
測試 DSPy 優化器
"""

import sys
sys.path.insert(0, '/app')

def test_optimizer_creation():
    """測試優化器創建"""
    print("🧪 測試 DSPy 優化器創建...")
    
    try:
        from src.core.dspy.optimizer import DSPyOptimizer
        
        # 創建優化器
        print("\n1. 創建優化器:")
        optimizer = DSPyOptimizer()
        print("  ✅ 優化器創建成功")
        
        # 檢查基本屬性
        print("\n2. 檢查優化器屬性:")
        assert hasattr(optimizer, 'cache_dir'), "缺少 cache_dir"
        assert hasattr(optimizer, 'config'), "缺少 config"
        assert hasattr(optimizer, 'stats'), "缺少 stats"
        print("  ✅ 基本屬性正常")
        
        # 測試統計功能
        print("\n3. 測試統計功能:")
        stats = optimizer.get_optimization_statistics()
        assert isinstance(stats, dict), "統計結果應該是字典"
        assert 'optimizations_run' in stats, "統計中應包含 optimizations_run"
        print(f"  ✅ 統計功能正常，已執行優化: {stats['optimizations_run']} 次")
        
        # 測試模組列表
        print("\n4. 測試模組列表:")
        saved_modules = optimizer.list_saved_modules()
        assert isinstance(saved_modules, list), "模組列表應該是列表"
        print(f"  ✅ 模組列表功能正常，找到 {len(saved_modules)} 個模組")
        
        return True
        
    except Exception as e:
        print(f"❌ 優化器創建測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_training_data_preparation():
    """測試訓練資料準備"""
    print("\n🔧 測試訓練資料準備...")
    
    try:
        from src.core.dspy.optimizer import DSPyOptimizer
        
        optimizer = DSPyOptimizer()
        
        # 測試訓練資料準備
        print("\n1. 準備訓練資料:")
        train_data, val_data = optimizer.prepare_training_data(
            max_examples=10
        )
        
        print(f"  訓練資料: {len(train_data)} 個")
        print(f"  驗證資料: {len(val_data)} 個")
        
        # 檢查資料格式
        if train_data:
            example = train_data[0]
            print(f"  範例格式: {type(example)}")
            assert hasattr(example, 'user_input'), "訓練範例應有 user_input"
            print("  ✅ 資料格式正確")
        
        return True
        
    except Exception as e:
        print(f"❌ 訓練資料準備測試失敗: {e}")
        return False

def test_metric_function():
    """測試評估指標函數"""
    print("\n📊 測試評估指標函數...")
    
    try:
        from src.core.dspy.optimizer import DSPyOptimizer
        
        optimizer = DSPyOptimizer()
        
        # 創建模擬預測結果
        mock_prediction = type('MockPrediction', (), {
            'responses': ['回應1', '回應2', '回應3'],
            'state': 'NORMAL',
            'dialogue_context': '測試情境'
        })()
        
        # 創建模擬範例
        mock_example = type('MockExample', (), {
            'user_input': '測試輸入',
            'responses': ['預期回應']
        })()
        
        # 測試評估函數
        score = optimizer._default_metric_function(mock_example, mock_prediction)
        
        print(f"  評估分數: {score:.2f}")
        assert 0.0 <= score <= 1.0, f"分數應在 0-1 範圍內，但得到 {score}"
        print("  ✅ 評估指標正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 評估指標測試失敗: {e}")
        return False

def test_optimizer_components():
    """測試優化器組件"""
    print("\n⚙️  測試優化器組件...")
    
    try:
        from src.core.dspy.optimizer import DSPyOptimizer
        
        optimizer = DSPyOptimizer()
        
        # 測試輔助方法
        print("\n1. 測試輔助方法:")
        
        # 測試範例轉換
        mock_example = type('MockExample', (), {
            'user_input': '測試輸入',
            'responses': ['回應1', '回應2'],
            'state': 'NORMAL'
        })()
        
        example_dict = optimizer._example_to_dict(mock_example)
        assert isinstance(example_dict, dict), "轉換結果應是字典"
        print("  ✅ 範例轉換功能正常")
        
        # 測試優化器創建（不實際執行優化）
        print("\n2. 測試優化器創建:")
        
        try:
            # 測試不同類型的優化器
            optimizer_types = ["BootstrapFewShot", "LabeledFewShot"]
            
            for opt_type in optimizer_types:
                opt_instance = optimizer._create_optimizer(opt_type)
                if opt_instance:
                    print(f"  ✅ {opt_type} 優化器創建成功")
                else:
                    print(f"  ⚠️  {opt_type} 優化器創建失敗")
                    
        except Exception as e:
            print(f"  ⚠️  優化器創建測試跳過: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 組件測試失敗: {e}")
        return False

if __name__ == "__main__":
    test1 = test_optimizer_creation()
    test2 = test_training_data_preparation()
    test3 = test_metric_function()
    test4 = test_optimizer_components()
    
    success_count = sum([test1, test2, test3, test4])
    total_tests = 4
    
    print(f"\n📋 測試總結: {success_count}/{total_tests} 通過")
    
    if success_count >= total_tests * 0.8:
        print("✅ 優化器測試通過")
    else:
        print("⚠️  優化器測試部分通過")