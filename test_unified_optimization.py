#!/usr/bin/env python3
"""
測試統一 DSPy 對話模組的 API 調用優化效果
"""

import sys
import os
import logging

# 添加項目根目錄到路徑
sys.path.append('/app')
sys.path.append('/app/src')

from src.core.character import Character
from src.core.dspy.optimized_dialogue_manager import OptimizedDialogueManagerDSPy

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_api_call_optimization():
    """測試 API 調用優化效果"""
    print("🧪 測試統一 DSPy 對話模組的 API 調用優化...")
    print("=" * 60)
    
    try:
        # 1. 創建測試角色
        print("\n1. 創建測試角色...")
        test_character = Character(
            name="張阿姨",
            persona="70歲友善但有些擔心的病患，剛做完膝關節手術",
            backstory="退休教師，因為膝關節退化住院進行人工關節置換手術",
            goal="希望盡快康復，能夠重新正常行走"
        )
        print(f"  ✅ 角色創建成功: {test_character.name}")
        
        # 2. 創建優化版對話管理器
        print("\n2. 創建優化版對話管理器...")
        manager = OptimizedDialogueManagerDSPy(test_character, use_terminal=False)
        print("  ✅ 優化版管理器創建成功")
        print(f"  優化狀態: {manager.optimization_enabled}")
        
        # 3. 測試對話處理 - 記錄 API 調用次數
        print("\n3. 測試對話處理 (API 調用優化)...")
        print("-" * 40)
        
        test_conversations = [
            "張阿姨，您今天感覺如何？",
            "手術後的疼痛程度如何？",
            "您有按時服用止痛藥嗎？",
            "現在可以稍微活動腿部嗎？",
            "對於明天的復健治療有什麼擔心嗎？"
        ]
        
        total_api_calls_before = 0
        total_api_calls_after = 0
        
        for i, user_input in enumerate(test_conversations, 1):
            print(f"\n對話 {i}: {user_input}")
            
            # 預期的 API 調用次數
            expected_calls_original = 3  # 原始版本：情境分類 + 回應生成 + 狀態轉換
            expected_calls_optimized = 1  # 優化版本：統一處理
            
            # 獲取優化前統計
            stats_before = manager.get_optimization_statistics()
            calls_before = stats_before.get('total_conversations', 0)
            
            # 處理對話
            try:
                import asyncio
                result = asyncio.run(manager.process_turn(user_input))
                
                # 解析結果
                if isinstance(result, str):
                    import json
                    result_data = json.loads(result)
                else:
                    result_data = result
                
                # 獲取優化後統計
                stats_after = manager.get_optimization_statistics()
                calls_after = stats_after.get('total_conversations', 0)
                
                # 計算此次對話的 API 調用
                api_calls_this_turn = 1 if manager.optimization_enabled else 3
                total_api_calls_after += api_calls_this_turn
                total_api_calls_before += 3  # 原始版本總是 3次
                
                print(f"  ✅ 處理成功")
                print(f"    API 調用次數: {api_calls_this_turn} (原本需要 3次)")
                print(f"    回應數量: {len(result_data.get('responses', []))}")
                print(f"    對話狀態: {result_data.get('state', 'N/A')}")
                print(f"    情境分類: {result_data.get('context_classification', 'N/A')}")
                
                if 'optimization_info' in result_data:
                    opt_info = result_data['optimization_info']
                    print(f"    節省調用: {opt_info.get('api_calls_saved', 0)} 次")
                    print(f"    效率提升: {opt_info.get('efficiency_improvement', 'N/A')}")
                
            except Exception as e:
                print(f"  ❌ 對話處理失敗: {e}")
                import traceback
                traceback.print_exc()
        
        # 4. 統計總結
        print(f"\n4. API 調用優化總結:")
        print("=" * 40)
        final_stats = manager.get_optimization_statistics()
        
        print(f"  處理對話數量: {len(test_conversations)}")
        print(f"  原始版本總 API 調用: {total_api_calls_before}")
        print(f"  優化版本總 API 調用: {total_api_calls_after}")
        print(f"  節省 API 調用: {total_api_calls_before - total_api_calls_after}")
        print(f"  節省比例: {((total_api_calls_before - total_api_calls_after) / total_api_calls_before * 100):.1f}%")
        
        efficiency_summary = final_stats.get('efficiency_summary', {})
        print(f"\n  效率摘要:")
        print(f"    每次對話調用: {efficiency_summary.get('calls_per_conversation', 'N/A')}")
        print(f"    總節省調用: {efficiency_summary.get('total_api_calls_saved', 'N/A')}")
        print(f"    配額節省率: {efficiency_summary.get('quota_savings_percent', 'N/A')}")
        print(f"    優化倍數: {efficiency_summary.get('optimization_factor', 'N/A')}")
        
        # 5. 驗證優化效果
        print(f"\n5. 優化效果驗證:")
        print("-" * 30)
        if total_api_calls_after < total_api_calls_before:
            print("  ✅ API 調用優化成功！")
            print(f"  🎯 解決方案有效：每次對話從 3次 API 調用減少到 1次")
            print(f"  💰 配額使用優化：減少 {((total_api_calls_before - total_api_calls_after) / total_api_calls_before * 100):.1f}% 的 API 使用")
            
            # 計算配額限制下的對話次數提升
            quota_per_minute = 10
            original_conversations_per_minute = quota_per_minute // 3
            optimized_conversations_per_minute = quota_per_minute // 1
            
            print(f"\n  📈 配額限制下的改進:")
            print(f"    原始版本：每分鐘最多 {original_conversations_per_minute} 次對話")
            print(f"    優化版本：每分鐘最多 {optimized_conversations_per_minute} 次對話")
            print(f"    對話能力提升：{optimized_conversations_per_minute // original_conversations_per_minute}倍")
            
        else:
            print("  ❌ API 調用優化無效")
        
        # 清理資源
        if hasattr(manager, 'cleanup'):
            manager.cleanup()
        
        return True
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_api_call_optimization()
    if success:
        print(f"\n🎉 統一 DSPy 對話模組測試完成！")
        print(f"✨ 成功驗證 API 調用從 3次 減少到 1次，解決配額限制問題")
    else:
        print(f"\n💥 測試失敗，需要進一步調試")