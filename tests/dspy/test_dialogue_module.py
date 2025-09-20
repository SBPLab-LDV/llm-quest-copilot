#!/usr/bin/env python3
"""
測試 DSPy 對話模組
"""

import sys
sys.path.insert(0, '/app')

def test_dialogue_module():
    """測試 DSPy 對話模組"""
    print("🧪 測試 DSPy 對話模組...")
    
    try:
        from src.core.dspy.dialogue_module import DSPyDialogueModule
        
        # 創建模組
        print("\n1. 創建對話模組:")
        module = DSPyDialogueModule()
        print("  ✅ 模組創建成功")
        
        # 測試基本功能
        print("\n2. 測試模組初始化:")
        print(f"  context_classifier: {type(module.context_classifier)}")
        print(f"  response_generator: {type(module.response_generator)}")
        print(f"  example_selector: {type(module.example_selector)}")
        
        # 測試簡單對話處理
        print("\n3. 測試對話處理:")
        test_cases = [
            {
                'user_input': '你今天感覺如何？',
                'character_name': '張先生',
                'character_persona': '友善的病患',
                'character_backstory': '住院中',
                'character_goal': '早日康復',
                'character_details': '',
                'conversation_history': []
            },
            {
                'user_input': '血壓測量完了',
                'character_name': '李太太',
                'character_persona': '有些擔心的病患',
                'character_backstory': '第一次住院',
                'character_goal': '了解病情',
                'character_details': '',
                'conversation_history': ['護理人員: 您好', '病患: 您好']
            }
        ]
        
        successful_tests = 0
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n  測試案例 {i}: {test_case['user_input']}")
            try:
                result = module(**test_case)
                
                print(f"    ✅ 處理成功")
                print(f"    回應數量: {len(result.responses)}")
                print(f"    對話狀態: {result.state}")
                print(f"    情境: {result.dialogue_context}")
                
                # 顯示前兩個回應
                for j, response in enumerate(result.responses[:2], 1):
                    print(f"    回應{j}: {response[:40]}...")
                
                successful_tests += 1
                
            except Exception as e:
                print(f"    ❌ 處理失敗: {e}")
        
        print(f"\n  成功測試: {successful_tests}/{len(test_cases)}")
        
        # 測試統計功能
        print("\n4. 統計資訊:")
        stats = module.get_statistics()
        print(f"  總調用次數: {stats['total_calls']}")
        print(f"  成功率: {stats['success_rate']:.2%}")
        print(f"  情境預測: {dict(list(stats['context_predictions'].items())[:3])}")
        
        # 測試錯誤處理
        print("\n5. 測試錯誤處理:")
        try:
            # 傳入無效參數測試錯誤處理
            error_result = module(
                user_input="",  # 空輸入
                character_name="",
                character_persona="",
                character_backstory="",
                character_goal="",
                character_details="",
                conversation_history=[]
            )
            print(f"  ✅ 錯誤處理正常，狀態: {error_result.state}")
        except Exception as e:
            print(f"  ⚠️  錯誤處理異常: {e}")
        
        # 清理資源
        print("\n6. 清理資源:")
        module.cleanup()
        print("  ✅ 資源清理完成")
        
        if successful_tests >= len(test_cases) * 0.8:  # 80% 成功率
            print("\n✅ DSPy 對話模組測試通過")
            return True
        else:
            print("\n⚠️  DSPy 對話模組測試部分通過")
            return False
        
    except Exception as e:
        print(f"❌ 對話模組測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_dialogue_module()