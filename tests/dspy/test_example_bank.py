#!/usr/bin/env python3
"""
測試 DSPy 範例銀行
"""

import sys
sys.path.insert(0, '/app')

def test_example_bank():
    """測試範例銀行功能"""
    print("🧪 測試 DSPy 範例銀行...")
    
    try:
        # 修正導入路徑
        from src.core.dspy.example_bank import ExampleBank
        
        # 創建範例銀行
        print("\n1. 創建範例銀行:")
        bank = ExampleBank()
        
        # 載入範例
        print("\n2. 載入範例:")
        if bank.load_all_examples():
            print(f"  ✅ 成功載入 {bank.stats['total_examples']} 個範例")
        else:
            print("  ❌ 範例載入失敗")
            return False
        
        # 計算嵌入向量
        print("\n3. 計算嵌入向量:")
        if bank.compute_embeddings():
            print("  ✅ 嵌入向量計算完成")
        else:
            print("  ❌ 嵌入向量計算失敗")
        
        # 測試檢索
        print("\n4. 測試檢索:")
        
        # 情境檢索
        context_examples = bank.get_relevant_examples(
            "測試", context="vital_signs_examples", k=3, strategy="context"
        )
        print(f"  情境檢索: {len(context_examples)} 個範例")
        if context_examples:
            print(f"    第一個範例: {getattr(context_examples[0], 'user_input', 'N/A')}")
        
        # 相似度檢索
        similarity_examples = bank.get_relevant_examples(
            "你發燒了嗎", k=3, strategy="similarity"
        )
        print(f"  相似度檢索: {len(similarity_examples)} 個範例")
        if similarity_examples:
            print(f"    第一個範例: {getattr(similarity_examples[0], 'user_input', 'N/A')}")
        
        # 混合檢索
        hybrid_examples = bank.get_relevant_examples(
            "血壓高", context="vital_signs", k=3, strategy="hybrid"
        )
        print(f"  混合檢索: {len(hybrid_examples)} 個範例")
        
        # 顯示統計
        print("\n5. 統計資訊:")
        stats = bank.get_bank_statistics()
        print(f"  總情境數: {stats['contexts']}")
        print(f"  總範例數: {stats['total_examples']}")
        print(f"  有嵌入向量: {stats['has_embeddings']}")
        
        # 顯示情境詳情
        print("\n6. 情境詳情:")
        for context, details in stats['context_details'].items():
            print(f"  {context}: {details['count']} 個範例")
        
        print("\n✅ 範例銀行測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 範例銀行測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_example_bank()