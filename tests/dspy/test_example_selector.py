#!/usr/bin/env python3
"""
測試 DSPy 範例選擇器
"""

import sys
sys.path.insert(0, '/app')

def test_example_selector():
    """測試範例選擇器功能"""
    print("🧪 測試 DSPy 範例選擇器...")
    
    try:
        from src.core.dspy.example_selector import ExampleSelector
        
        # 創建選擇器
        print("\n1. 創建範例選擇器:")
        selector = ExampleSelector()
        
        if not selector.example_bank.all_examples:
            print("  ❌ 範例銀行為空，無法進行測試")
            return False
        
        print(f"  ✅ 選擇器創建成功，載入 {len(selector.example_bank.all_examples)} 個範例")
        
        # 測試基本選擇功能
        print("\n2. 測試基本選擇功能:")
        
        test_cases = [
            ("發燒", "vital_signs_examples", "context"),
            ("血壓高", None, "similarity"),
            ("傷口", "wound_tube_care_examples", "hybrid"),
            ("復健", None, "adaptive")
        ]
        
        for query, context, strategy in test_cases:
            print(f"\n  測試: {query} (情境: {context}, 策略: {strategy})")
            try:
                examples = selector.select_examples(
                    query, context=context, k=3, strategy=strategy
                )
                print(f"    ✅ 返回 {len(examples)} 個範例")
                
                if examples:
                    for i, example in enumerate(examples):
                        user_input = getattr(example, 'user_input', 'N/A')
                        dialogue_context = getattr(example, 'dialogue_context', 'N/A')
                        print(f"      {i+1}. {user_input[:40]}... ({dialogue_context})")
                        
            except Exception as e:
                print(f"    ❌ 測試失敗: {e}")
        
        # 測試所有策略
        print("\n3. 測試所有可用策略:")
        available_strategies = selector.get_selection_strategies()
        print(f"  可用策略: {available_strategies}")
        
        for strategy in available_strategies[:4]:  # 測試前 4 個策略
            try:
                examples = selector.select_examples(
                    "你好嗎？", k=2, strategy=strategy
                )
                print(f"  {strategy}: {len(examples)} 個範例")
            except Exception as e:
                print(f"  {strategy}: 失敗 - {e}")
        
        # 測試多樣性
        print("\n4. 測試多樣性:")
        examples = selector.select_examples(
            "疼痛", k=5, strategy="balanced"
        )
        if examples:
            contexts = [getattr(ex, 'dialogue_context', 'unknown') for ex in examples]
            unique_contexts = set(contexts)
            print(f"  5 個範例來自 {len(unique_contexts)} 個不同情境")
            print(f"  情境分佈: {dict((ctx, contexts.count(ctx)) for ctx in unique_contexts)}")
        
        # 測試性能指標
        print("\n5. 性能指標:")
        metrics = selector.get_performance_metrics()
        if metrics:
            print(f"  總選擇次數: {metrics.get('total_selections', 0)}")
            print(f"  成功率: {metrics.get('success_rate', 0):.2%}")
            strategy_usage = metrics.get('strategy_usage', {})
            if strategy_usage:
                print("  策略使用統計:")
                for strategy, count in strategy_usage.items():
                    print(f"    {strategy}: {count} 次")
        
        print("\n✅ 範例選擇器測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 範例選擇器測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_example_selector()