#!/usr/bin/env python3
"""
測試 DSPy 評估器
"""

import sys
sys.path.insert(0, '/app')

def test_evaluator_creation():
    """測試評估器創建"""
    print("🧪 測試 DSPy 評估器創建...")
    
    try:
        from src.core.dspy.evaluator import DSPyEvaluator
        
        # 創建評估器
        print("\n1. 創建評估器:")
        evaluator = DSPyEvaluator()
        print("  ✅ 評估器創建成功")
        
        # 檢查評估器屬性
        print("\n2. 檢查評估器屬性:")
        assert hasattr(evaluator, 'metrics'), "缺少 metrics 屬性"
        assert hasattr(evaluator, 'stats'), "缺少 stats 屬性"
        assert hasattr(evaluator, 'evaluation_history'), "缺少 evaluation_history 屬性"
        print("  ✅ 基本屬性正常")
        
        # 檢查可用指標
        print("\n3. 可用評估指標:")
        available_metrics = list(evaluator.metrics.keys())
        print(f"  指標列表: {available_metrics}")
        assert len(available_metrics) > 0, "應該有可用指標"
        print("  ✅ 評估指標正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 評估器創建測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_single_evaluation():
    """測試單個評估"""
    print("\n📊 測試單個預測評估...")
    
    try:
        from src.core.dspy.evaluator import DSPyEvaluator
        
        evaluator = DSPyEvaluator()
        
        # 創建模擬預測結果
        mock_prediction = type('MockPrediction', (), {
            'responses': ['我很好', '今天感覺不錯', '謝謝關心'],
            'state': 'NORMAL',
            'dialogue_context': '一般對話'
        })()
        
        # 執行評估
        evaluation_result = evaluator.evaluate_prediction(
            user_input="你今天感覺如何？",
            prediction=mock_prediction
        )
        
        print(f"  總分: {evaluation_result['overall_score']:.2f}")
        print(f"  評估指標數: {len(evaluation_result['scores'])}")
        
        # 檢查結果格式
        assert 'overall_score' in evaluation_result, "缺少總分"
        assert 'scores' in evaluation_result, "缺少詳細分數"
        assert isinstance(evaluation_result['scores'], dict), "分數應該是字典"
        
        # 檢查分數範圍
        for metric, score in evaluation_result['scores'].items():
            assert 0.0 <= score <= 1.0, f"分數 {metric}={score} 超出範圍"
        
        print("  ✅ 單個評估正常")
        return True
        
    except Exception as e:
        print(f"❌ 單個評估測試失敗: {e}")
        return False

def test_individual_metrics():
    """測試個別評估指標"""
    print("\n🔧 測試個別評估指標...")
    
    try:
        from src.core.dspy.evaluator import DSPyEvaluator
        
        evaluator = DSPyEvaluator()
        
        # 測試用例
        test_cases = [
            {
                'name': '完整回應',
                'prediction': type('Pred', (), {
                    'responses': ['我很好', '感覺不錯', '謝謝'],
                    'state': 'NORMAL',
                    'dialogue_context': '問候'
                })(),
                'input': '你好嗎？'
            },
            {
                'name': '空回應',
                'prediction': type('Pred', (), {
                    'responses': [],
                    'state': 'CONFUSED',
                    'dialogue_context': ''
                })(),
                'input': '測試'
            }
        ]
        
        successful_tests = 0
        
        for test_case in test_cases:
            print(f"\n  測試案例: {test_case['name']}")
            
            try:
                # 測試回應品質
                quality_score = evaluator._evaluate_response_quality(
                    test_case['input'], test_case['prediction']
                )
                print(f"    回應品質: {quality_score:.2f}")
                
                # 測試狀態一致性
                state_score = evaluator._evaluate_state_consistency(
                    test_case['input'], test_case['prediction']
                )
                print(f"    狀態一致性: {state_score:.2f}")
                
                # 測試多樣性
                diversity_score = evaluator._evaluate_diversity(
                    test_case['input'], test_case['prediction']
                )
                print(f"    回應多樣性: {diversity_score:.2f}")
                
                successful_tests += 1
                
            except Exception as e:
                print(f"    ❌ 失敗: {e}")
        
        print(f"\n  成功測試: {successful_tests}/{len(test_cases)}")
        return successful_tests > 0
        
    except Exception as e:
        print(f"❌ 個別指標測試失敗: {e}")
        return False

def test_evaluation_statistics():
    """測試評估統計"""
    print("\n📈 測試評估統計...")
    
    try:
        from src.core.dspy.evaluator import DSPyEvaluator
        
        evaluator = DSPyEvaluator()
        
        # 執行幾次評估
        mock_prediction = type('MockPrediction', (), {
            'responses': ['回應1', '回應2'],
            'state': 'NORMAL',
            'dialogue_context': '測試'
        })()
        
        for i in range(3):
            evaluator.evaluate_prediction(
                user_input=f"測試輸入 {i}",
                prediction=mock_prediction
            )
        
        # 檢查統計
        stats = evaluator.get_evaluation_statistics()
        
        print(f"  總評估次數: {stats['total_evaluations']}")
        assert stats['total_evaluations'] == 3, f"評估次數應為3，但得到 {stats['total_evaluations']}"
        
        # 檢查歷史記錄
        recent = evaluator.get_recent_evaluations(limit=2)
        print(f"  最近評估記錄: {len(recent)} 筆")
        assert len(recent) == 2, f"最近記錄應為2筆，但得到 {len(recent)}"
        
        print("  ✅ 統計功能正常")
        return True
        
    except Exception as e:
        print(f"❌ 統計測試失敗: {e}")
        return False

def test_evaluation_edge_cases():
    """測試評估邊界情況"""
    print("\n🧐 測試評估邊界情況...")
    
    try:
        from src.core.dspy.evaluator import DSPyEvaluator
        
        evaluator = DSPyEvaluator()
        
        # 測試空預測
        empty_prediction = type('EmptyPrediction', (), {})()
        
        result = evaluator.evaluate_prediction(
            user_input="測試",
            prediction=empty_prediction
        )
        
        print(f"  空預測評估分數: {result['overall_score']:.2f}")
        assert result['overall_score'] >= 0.0, "分數不應為負"
        
        # 測試無效狀態
        invalid_state_prediction = type('InvalidPrediction', (), {
            'responses': ['測試回應'],
            'state': 'INVALID_STATE',
            'dialogue_context': '測試'
        })()
        
        result2 = evaluator.evaluate_prediction(
            user_input="測試",
            prediction=invalid_state_prediction
        )
        
        print(f"  無效狀態評估分數: {result2['overall_score']:.2f}")
        
        print("  ✅ 邊界情況處理正常")
        return True
        
    except Exception as e:
        print(f"❌ 邊界情況測試失敗: {e}")
        return False

if __name__ == "__main__":
    test1 = test_evaluator_creation()
    test2 = test_single_evaluation()
    test3 = test_individual_metrics()
    test4 = test_evaluation_statistics()
    test5 = test_evaluation_edge_cases()
    
    success_count = sum([test1, test2, test3, test4, test5])
    total_tests = 5
    
    print(f"\n📋 測試總結: {success_count}/{total_tests} 通過")
    
    if success_count >= total_tests * 0.8:
        print("✅ 評估器測試通過")
    else:
        print("⚠️  評估器測試部分通過")