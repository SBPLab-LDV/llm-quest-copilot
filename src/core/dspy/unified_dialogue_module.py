#!/usr/bin/env python3
"""
統一 DSPy 對話模組

將原本的多步驟調用（情境分類、回應生成、狀態轉換）合併為單一 API 調用，
以解決 API 配額限制問題。
"""

import dspy
import json
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from .dialogue_module import DSPyDialogueModule
from .signatures import PatientResponseSignature

logger = logging.getLogger(__name__)


class UnifiedPatientResponseSignature(dspy.Signature):
    """統一的病患回應生成簽名
    
    將情境分類、回應生成、狀態判斷合併為單一調用，
    減少 API 使用次數從 3次 降低到 1次。
    """
    
    # 輸入欄位 - 護理人員和對話相關信息
    user_input = dspy.InputField(desc="護理人員的輸入或問題")
    character_name = dspy.InputField(desc="病患角色的名稱")
    character_persona = dspy.InputField(desc="病患的個性描述")
    character_backstory = dspy.InputField(desc="病患的背景故事")
    character_goal = dspy.InputField(desc="病患的目標")
    character_details = dspy.InputField(desc="病患的詳細設定，包含固定和浮動設定的YAML格式字符串")
    conversation_history = dspy.InputField(desc="最近的對話歷史，以換行分隔")
    available_contexts = dspy.InputField(desc="可用的對話情境列表")
    
    # 輸出欄位 - 統一的回應結果
    reasoning = dspy.OutputField(desc="推理過程：包含情境分析、回應思考和狀態評估")
    context_classification = dspy.OutputField(desc="對話情境分類：vital_signs_examples, daily_routine_examples, treatment_examples 等")
    confidence = dspy.OutputField(desc="情境分類的信心度，0.0到1.0之間")
    responses = dspy.OutputField(desc="5個不同的病患回應選項，每個都應該是完整的句子，格式為JSON陣列")
    state = dspy.OutputField(desc="對話狀態：必須是 NORMAL、CONFUSED、TRANSITIONING 或 TERMINATED 其中之一")
    dialogue_context = dspy.OutputField(desc="當前對話情境描述，如：醫師查房、病房日常、生命徵象相關、身體評估等")
    state_reasoning = dspy.OutputField(desc="狀態判斷的理由說明")


class UnifiedDSPyDialogueModule(DSPyDialogueModule):
    """統一的 DSPy 對話模組
    
    優化版本：將多步驟調用合併為單一 API 調用，解決配額限制問題。
    繼承原有接口，保持完全的 API 兼容性。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化統一對話模組
        
        Args:
            config: 配置字典
        """
        # 初始化父類，DSPyDialogueModule 只接受 config 參數
        super().__init__(config)
        
        # 替換為統一的對話處理器
        self.unified_response_generator = dspy.ChainOfThought(UnifiedPatientResponseSignature)
        
        # 統計信息
        self.unified_stats = {
            'api_calls_saved': 0,
            'total_unified_calls': 0,
            'success_rate': 0.0,
            'last_reset': datetime.now().isoformat()
        }
        
        logger.info("UnifiedDSPyDialogueModule 初始化完成 - 已優化為單一 API 調用")
    
    def forward(self, user_input: str, character_name: str, character_persona: str,
                character_backstory: str, character_goal: str, character_details: str,
                conversation_history: List[str]) -> dspy.Prediction:
        """統一的前向傳播 - 單次 API 調用完成所有處理
        
        Args:
            user_input: 護理人員的輸入
            character_name: 病患名稱
            character_persona: 病患個性
            character_backstory: 病患背景故事
            character_goal: 病患目標
            character_details: 病患詳細設定
            conversation_history: 對話歷史
            
        Returns:
            DSPy Prediction 包含所有回應資訊
        """
        try:
            self.stats['total_calls'] += 1
            self.unified_stats['total_unified_calls'] += 1
            
            # 格式化對話歷史
            formatted_history = "\n".join(conversation_history[-5:])
            
            # 獲取可用情境（本地處理，不調用 API）
            available_contexts = self._get_available_contexts()
            
            # ====== 統一日誌追蹤 ======
            logger.info(f"=== UNIFIED DSPy CALL (節省 2次 API 調用) ===")
            logger.info(f"Input parameters:")
            logger.info(f"  user_input: {user_input}")
            logger.info(f"  character_name: {character_name}")
            logger.info(f"  character_persona: {character_persona}")
            logger.info(f"  formatted_history: {formatted_history}")
            logger.info(f"=== 單次調用處理：情境分類 + 回應生成 + 狀態判斷 ===")
            
            # **關鍵優化：單一 API 調用完成所有處理**
            unified_prediction = self.unified_response_generator(
                user_input=user_input,
                character_name=character_name,
                character_persona=character_persona,
                character_backstory=character_backstory,
                character_goal=character_goal,
                character_details=character_details,
                conversation_history=formatted_history,
                available_contexts=available_contexts
            )
            
            # ====== 統一結果日誌 ======
            logger.info(f"=== UNIFIED DSPy RESULT ===")
            logger.info(f"  context_classification: {unified_prediction.context_classification}")
            logger.info(f"  confidence: {unified_prediction.confidence}")
            logger.info(f"  responses count: {len(self._parse_responses(unified_prediction.responses))}")
            logger.info(f"  state: {unified_prediction.state}")
            logger.info(f"  dialogue_context: {unified_prediction.dialogue_context}")
            logger.info(f"=== API 調用節省：2次 (原本需要 3次，現在只需 1次) ===")
            
            # 處理回應格式
            responses = self._process_responses(unified_prediction.responses)
            
            # 更新統計 - 計算節省的 API 調用
            self.unified_stats['api_calls_saved'] += 2  # 原本 3次，現在 1次，節省 2次
            self._update_stats(unified_prediction.context_classification, unified_prediction.state)
            self.stats['successful_calls'] += 1
            
            # 組合最終結果
            final_prediction = dspy.Prediction(
                user_input=user_input,
                responses=responses,
                state=unified_prediction.state,
                dialogue_context=unified_prediction.dialogue_context,
                confidence=getattr(unified_prediction, 'confidence', 1.0),
                context_classification=unified_prediction.context_classification,
                examples_used=0,  # 統一模式下暫不使用範例
                processing_info={
                    'unified_call': True,
                    'api_calls_saved': 2,
                    'context_classification': unified_prediction.context_classification,
                    'state_reasoning': getattr(unified_prediction, 'state_reasoning', ''),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            # 更新成功率
            self.unified_stats['success_rate'] = (
                self.stats['successful_calls'] / self.stats['total_calls']
                if self.stats['total_calls'] > 0 else 0
            )
            
            logger.info(f"統一對話處理成功 - API 調用節省率: 66.7% (1次 vs 3次)")
            return final_prediction
            
        except Exception as e:
            self.stats['failed_calls'] += 1
            logger.error(f"=== UNIFIED DSPy CALL FAILED ===")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception message: {str(e)}")
            logger.error(f"Input that caused failure:")
            logger.error(f"  user_input: {user_input}")
            logger.error(f"  character_name: {character_name}")
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            logger.error(f"=== END UNIFIED DSPy FAILURE ===")
            
            # 返回錯誤回應
            return self._create_error_response(user_input, str(e))
    
    def _parse_responses(self, responses_text: str) -> List[str]:
        """解析回應文本為列表"""
        try:
            if isinstance(responses_text, str):
                # 嘗試解析 JSON
                try:
                    parsed = json.loads(responses_text)
                    if isinstance(parsed, list):
                        return parsed[:5]  # 最多5個回應
                except json.JSONDecodeError:
                    # 不是 JSON，按行分割
                    lines = [line.strip() for line in responses_text.split('\n') if line.strip()]
                    return lines[:5]
            return [str(responses_text)]
        except Exception as e:
            logger.warning(f"回應解析失敗: {e}")
            return ["回應格式解析失敗"]
    
    def get_unified_statistics(self) -> Dict[str, Any]:
        """獲取統一模組的統計資訊"""
        base_stats = self.get_dspy_statistics() if hasattr(self, 'get_dspy_statistics') else {}
        
        unified_stats = {
            **base_stats,
            **self.unified_stats,
            'api_efficiency': {
                'calls_per_conversation': 1,  # 統一模式：每次對話僅1次調用
                'original_calls_per_conversation': 3,  # 原始模式：每次對話3次調用
                'efficiency_improvement': '66.7%',
                'total_calls_saved': self.unified_stats['api_calls_saved']
            }
        }
        
        return unified_stats
    
    def reset_unified_statistics(self):
        """重置統一模組統計"""
        self.reset_statistics()  # 重置父類統計
        self.unified_stats = {
            'api_calls_saved': 0,
            'total_unified_calls': 0,
            'success_rate': 0.0,
            'last_reset': datetime.now().isoformat()
        }


# 工廠函數
def create_optimized_dialogue_module(config: Optional[Dict[str, Any]] = None) -> UnifiedDSPyDialogueModule:
    """創建優化的統一對話模組
    
    Args:
        config: 配置字典
        
    Returns:
        配置好的 UnifiedDSPyDialogueModule
    """
    try:
        module = UnifiedDSPyDialogueModule(config)
        return module
    except Exception as e:
        logger.error(f"創建統一對話模組失敗: {e}")
        raise


# 測試函數
def test_unified_dialogue_module():
    """測試統一對話模組的 API 調用節省效果"""
    print("🧪 測試統一 DSPy 對話模組...")
    
    try:
        # 創建統一模組
        print("\n1. 創建統一對話模組:")
        module = create_optimized_dialogue_module()
        print("  ✅ 統一模組創建成功")
        
        # 測試對話處理
        print("\n2. 測試統一對話處理 (僅1次API調用):")
        test_input = "你今天感覺如何？"
        
        result = module(
            user_input=test_input,
            character_name="測試病患",
            character_persona="友善但有些擔心的病患",
            character_backstory="住院中的老人",
            character_goal="康復出院",
            character_details="",
            conversation_history=[]
        )
        
        print(f"  ✅ 統一處理成功")
        print(f"    用戶輸入: {test_input}")
        print(f"    回應數量: {len(result.responses)}")
        print(f"    對話狀態: {result.state}")
        print(f"    情境分類: {result.context_classification}")
        print(f"    API 調用節省: {result.processing_info.get('api_calls_saved', 0)} 次")
        
        # 測試統計功能
        print("\n3. API 調用節省統計:")
        stats = module.get_unified_statistics()
        print(f"  總調用次數: {stats.get('total_unified_calls', 0)}")
        print(f"  節省的調用次數: {stats.get('api_calls_saved', 0)}")
        print(f"  效率提升: {stats.get('api_efficiency', {}).get('efficiency_improvement', 'N/A')}")
        print(f"  成功率: {stats.get('success_rate', 0):.2%}")
        
        print("\n✅ 統一 DSPy 對話模組測試完成")
        print(f"🎯 關鍵優化：API 調用從 3次 減少到 1次，節省 66.7% 的配額使用！")
        return True
        
    except Exception as e:
        print(f"❌ 統一模組測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_unified_dialogue_module()