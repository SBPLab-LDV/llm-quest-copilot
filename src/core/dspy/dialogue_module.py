"""
DSPy 對話模組

核心的 DSPy 對話模組，整合情境分類和回應生成功能。
使用 DSPy 的 ChainOfThought 和動態範例選擇。
"""

import dspy
from typing import List, Dict, Any, Optional, Union
import logging
import json
from datetime import datetime

# 避免相對導入問題
try:
    from .signatures import (
        PatientResponseSignature, 
        ContextClassificationSignature,
        ResponseEvaluationSignature,
        StateTransitionSignature
    )
    from .example_selector import ExampleSelector
    from .setup import initialize_dspy, cleanup_dspy
    from .config import DSPyConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from signatures import (
        PatientResponseSignature,
        ContextClassificationSignature, 
        ResponseEvaluationSignature,
        StateTransitionSignature
    )
    from example_selector import ExampleSelector
    from setup import initialize_dspy, cleanup_dspy
    from config import DSPyConfig

logger = logging.getLogger(__name__)

class DSPyDialogueModule(dspy.Module):
    """DSPy 對話模組
    
    核心的對話處理模組，使用 DSPy 的 Signatures 和 ChainOfThought
    來處理情境分類和回應生成。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 DSPy 對話模組
        
        Args:
            config: 配置字典 (可選)
        """
        super().__init__()
        
        # 載入配置
        self.config_manager = DSPyConfig()
        self.config = config or self.config_manager.get_dspy_config()
        
        # 初始化 DSPy 系統
        self._initialize_dspy()
        
        # 創建子模組
        self.context_classifier = dspy.ChainOfThought(ContextClassificationSignature)
        self.response_generator = dspy.ChainOfThought(PatientResponseSignature)
        self.response_evaluator = dspy.ChainOfThought(ResponseEvaluationSignature)
        self.state_transition = dspy.ChainOfThought(StateTransitionSignature)
        
        # 範例選擇器
        self.example_selector = ExampleSelector()
        
        # 統計和監控
        self.stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'context_predictions': {},
            'state_transitions': {},
            'last_reset': datetime.now().isoformat()
        }
        
        logger.info("DSPyDialogueModule 初始化完成")
    
    def _initialize_dspy(self):
        """初始化 DSPy 環境"""
        try:
            if not initialize_dspy(self.config):
                logger.error("DSPy 初始化失敗")
                raise RuntimeError("DSPy 初始化失敗")
            logger.info("DSPy 環境初始化成功")
        except Exception as e:
            logger.error(f"DSPy 初始化錯誤: {e}")
            raise
    
    def forward(self, user_input: str, character_name: str, character_persona: str,
                character_backstory: str, character_goal: str, character_details: str,
                conversation_history: List[str]) -> dspy.Prediction:
        """前向傳播 - 處理對話輪次
        
        Args:
            user_input: 護理人員的輸入
            character_name: 病患名稱
            character_persona: 病患個性
            character_backstory: 病患背景故事
            character_goal: 病患目標
            character_details: 病患詳細設定
            conversation_history: 對話歷史
            
        Returns:
            DSPy Prediction 包含回應和相關資訊
        """
        try:
            self.stats['total_calls'] += 1
            
            # 步驟 1: 情境分類
            context_prediction = self._classify_context(
                user_input, conversation_history
            )
            
            # 步驟 2: 選擇相關範例
            relevant_examples = self._select_examples(
                user_input, context_prediction.context
            )
            
            # 步驟 3: 生成回應
            response_prediction = self._generate_response(
                user_input=user_input,
                character_name=character_name,
                character_persona=character_persona,
                character_backstory=character_backstory,
                character_goal=character_goal,
                character_details=character_details,
                conversation_history=conversation_history,
                relevant_examples=relevant_examples
            )
            
            # 步驟 4: 狀態轉換判斷 (可選)
            state_prediction = self._determine_state_transition(
                user_input, response_prediction.state, character_details
            )
            
            # 更新統計
            self._update_stats(context_prediction.context, response_prediction.state)
            self.stats['successful_calls'] += 1
            
            # 組合最終結果
            final_prediction = dspy.Prediction(
                user_input=user_input,
                responses=response_prediction.responses,
                state=state_prediction.new_state if hasattr(state_prediction, 'new_state') else response_prediction.state,
                dialogue_context=response_prediction.dialogue_context,
                confidence=context_prediction.confidence if hasattr(context_prediction, 'confidence') else 1.0,
                context_classification=context_prediction.context,
                examples_used=len(relevant_examples),
                processing_info={
                    'context_prediction': context_prediction,
                    'state_prediction': state_prediction if 'state_prediction' in locals() else None,
                    'examples_count': len(relevant_examples),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            logger.debug(f"對話處理成功，返回 {len(response_prediction.responses)} 個回應選項")
            return final_prediction
            
        except Exception as e:
            self.stats['failed_calls'] += 1
            logger.error(f"對話處理失敗: {e}")
            
            # 返回錯誤回應
            return self._create_error_response(user_input, str(e))
    
    def _classify_context(self, user_input: str, conversation_history: List[str]) -> dspy.Prediction:
        """對話情境分類
        
        Args:
            user_input: 用戶輸入
            conversation_history: 對話歷史
            
        Returns:
            情境分類結果
        """
        try:
            # 載入可用情境
            available_contexts = self._get_available_contexts()
            
            # 執行情境分類
            prediction = self.context_classifier(
                user_input=user_input,
                available_contexts=available_contexts,
                conversation_history="\n".join(conversation_history[-5:])  # 只使用最近5輪
            )
            
            logger.debug(f"情境分類結果: {prediction.context}")
            return prediction
            
        except Exception as e:
            logger.error(f"情境分類失敗: {e}")
            # 返回預設情境
            return dspy.Prediction(
                context="daily_routine_examples",
                confidence=0.5
            )
    
    def _select_examples(self, user_input: str, context: str) -> List[dspy.Example]:
        """選擇相關範例
        
        Args:
            user_input: 用戶輸入
            context: 對話情境
            
        Returns:
            相關範例列表
        """
        try:
            # 使用範例選擇器獲取相關範例
            examples = self.example_selector.select_examples(
                query=user_input,
                context=context,
                k=3,  # 選擇3個最相關的範例
                strategy="hybrid"
            )
            
            logger.debug(f"選擇了 {len(examples)} 個相關範例")
            return examples
            
        except Exception as e:
            logger.error(f"範例選擇失敗: {e}")
            return []
    
    def _generate_response(self, user_input: str, character_name: str,
                          character_persona: str, character_backstory: str,
                          character_goal: str, character_details: str,
                          conversation_history: List[str],
                          relevant_examples: List[dspy.Example]) -> dspy.Prediction:
        """生成病患回應
        
        Args:
            user_input: 用戶輸入
            character_name: 角色名稱
            character_persona: 角色個性
            character_backstory: 角色背景
            character_goal: 角色目標
            character_details: 角色詳細設定
            conversation_history: 對話歷史
            relevant_examples: 相關範例
            
        Returns:
            回應生成結果
        """
        try:
            # 格式化對話歷史
            formatted_history = "\n".join(conversation_history[-5:])
            
            # ====== 詳細日誌追蹤 - DSPy SIGNATURE EXECUTION ======
            logger.info(f"=== DSPy SIGNATURE EXECUTION ===")
            logger.info(f"Input parameters:")
            logger.info(f"  user_input: {user_input}")
            logger.info(f"  character_name: {character_name}")
            logger.info(f"  character_persona: {character_persona}")
            logger.info(f"  character_backstory: {character_backstory}")
            logger.info(f"  character_goal: {character_goal}")
            logger.info(f"  character_details: {character_details}")
            logger.info(f"  formatted_history: {formatted_history}")
            logger.info(f"  relevant_examples count: {len(relevant_examples)}")
            logger.info(f"=== CALLING DSPy PatientResponseSignature ===")
            
            # TODO: 將 relevant_examples 整合到 prompt 中
            # 目前先直接呼叫 response generator
            
            prediction = self.response_generator(
                user_input=user_input,
                character_name=character_name,
                character_persona=character_persona,
                character_backstory=character_backstory,
                character_goal=character_goal,
                character_details=character_details,
                conversation_history=formatted_history
            )
            
            # ====== 詳細日誌追蹤 - DSPy SIGNATURE RESULT ======
            logger.info(f"=== DSPy SIGNATURE PREDICTION RESULT ===")
            logger.info(f"  prediction type: {type(prediction)}")
            logger.info(f"  prediction attributes: {dir(prediction)}")
            if hasattr(prediction, 'responses'):
                logger.info(f"  responses: {prediction.responses}")
            if hasattr(prediction, 'state'):
                logger.info(f"  state: {prediction.state}")
            if hasattr(prediction, 'dialogue_context'):
                logger.info(f"  dialogue_context: {prediction.dialogue_context}")
            logger.info(f"=== END DSPy SIGNATURE RESULT ===")
            
            # 處理回應格式
            responses = self._process_responses(prediction.responses)
            
            # 更新 prediction
            processed_prediction = dspy.Prediction(
                responses=responses,
                state=prediction.state,
                dialogue_context=prediction.dialogue_context,
                raw_prediction=prediction
            )
            
            logger.debug(f"成功生成 {len(responses)} 個回應選項")
            return processed_prediction
            
        except Exception as e:
            # ====== 詳細異常日誌追蹤 ======
            logger.error(f"=== DSPy SIGNATURE EXECUTION FAILED ===")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception message: {str(e)}")
            logger.error(f"Input that caused failure:")
            logger.error(f"  user_input: {user_input}")
            logger.error(f"  character_name: {character_name}")
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            logger.error(f"=== END DSPy SIGNATURE FAILURE ===")
            
            # 返回預設回應 - 添加錯誤信息以便調試
            return dspy.Prediction(
                responses=[f"DSPySignatureError[{type(e).__name__}]: {e}"],
                state="ERROR",
                dialogue_context="DSPY_SIGNATURE_EXCEPTION",
                raw_prediction=None
            )
    
    def _determine_state_transition(self, user_input: str, current_state: str,
                                   character_condition: str) -> Optional[dspy.Prediction]:
        """判斷狀態轉換
        
        Args:
            user_input: 用戶輸入
            current_state: 當前狀態
            character_condition: 角色狀況
            
        Returns:
            狀態轉換預測 (可選)
        """
        try:
            # 只有在特定條件下才執行狀態轉換判斷
            if current_state not in ["NORMAL", "CONFUSED"]:
                return None
            
            prediction = self.state_transition(
                current_state=current_state,
                user_input=user_input,
                character_condition=character_condition,
                conversation_context="對話進行中"
            )
            
            logger.debug(f"狀態轉換判斷: {current_state} -> {prediction.new_state}")
            return prediction
            
        except Exception as e:
            logger.error(f"狀態轉換判斷失敗: {e}")
            return None
    
    def _process_responses(self, responses: Union[str, List[str]]) -> List[str]:
        """處理回應格式
        
        Args:
            responses: 原始回應 (可能是字串或列表)
            
        Returns:
            格式化的回應列表
        """
        try:
            if isinstance(responses, str):
                # 嘗試解析 JSON
                try:
                    parsed = json.loads(responses)
                    if isinstance(parsed, list):
                        return parsed[:4]  # 最多5個回應
                    else:
                        return [responses]
                except json.JSONDecodeError:
                    # 不是 JSON，按行分割
                    lines = [line.strip() for line in responses.split('\n') if line.strip()]
                    return lines[:4]
            elif isinstance(responses, list):
                return [str(r) for r in responses[:4]]
            else:
                return [str(responses)]
                
        except Exception as e:
            logger.error(f"回應格式處理失敗: {e}", exc_info=True)
            return [f"ResponseFormatError[{type(e).__name__}]: {e}"]
    
    def _get_available_contexts(self) -> str:
        """獲取可用情境列表
        
        Returns:
            情境列表的 YAML 格式字串
        """
        try:
            contexts = self.example_selector.example_bank.get_context_list()
            context_descriptions = {
                'vital_signs_examples': '生命徵象相關',
                'outpatient_examples': '門診醫師問診', 
                'treatment_examples': '治療相關',
                'physical_assessment_examples': '身體評估',
                'wound_tube_care_examples': '傷口管路相關',
                'rehabilitation_examples': '復健治療',
                'doctor_visit_examples': '醫師查房',
                'daily_routine_examples': '病房日常',
                'examination_examples': '檢查相關',
                'nutrition_examples': '營養相關'
            }
            
            result = []
            for context in contexts:
                description = context_descriptions.get(context, context)
                result.append(f"- {context}: {description}")
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"獲取情境列表失敗: {e}")
            return "- daily_routine_examples: 病房日常"
    
    def _update_stats(self, context: str, state: str):
        """更新統計資訊"""
        # 更新情境統計
        if context in self.stats['context_predictions']:
            self.stats['context_predictions'][context] += 1
        else:
            self.stats['context_predictions'][context] = 1
        
        # 更新狀態統計
        if state in self.stats['state_transitions']:
            self.stats['state_transitions'][state] += 1
        else:
            self.stats['state_transitions'][state] = 1
    
    def _create_error_response(self, user_input: str, error_message: str) -> dspy.Prediction:
        """創建錯誤回應

        Args:
            user_input: 原始用戶輸入
            error_message: 錯誤訊息

        Returns:
            錯誤回應預測
        """
        return dspy.Prediction(
            user_input=user_input,
            responses=[f"DSPyModuleError: {error_message}"],
            state="ERROR",
            dialogue_context="DSPY_MODULE_EXCEPTION",
            confidence=0.0,
            error=error_message,
            processing_info={
                'error_occurred': True,
                'error_message': error_message,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取模組統計資訊
        
        Returns:
            統計資訊字典
        """
        success_rate = (self.stats['successful_calls'] / self.stats['total_calls'] 
                       if self.stats['total_calls'] > 0 else 0)
        
        return {
            **self.stats,
            'success_rate': success_rate,
            'error_rate': 1 - success_rate,
            'most_common_context': max(self.stats['context_predictions'], 
                                     key=self.stats['context_predictions'].get) 
                                   if self.stats['context_predictions'] else None,
            'most_common_state': max(self.stats['state_transitions'],
                                   key=self.stats['state_transitions'].get)
                                 if self.stats['state_transitions'] else None
        }
    
    def reset_statistics(self):
        """重置統計資訊"""
        self.stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'context_predictions': {},
            'state_transitions': {},
            'last_reset': datetime.now().isoformat()
        }
        
        # 同時重置範例選擇器統計
        if hasattr(self.example_selector, 'reset_metrics'):
            self.example_selector.reset_metrics()
    
    def cleanup(self):
        """清理資源"""
        try:
            cleanup_dspy()
            logger.info("DSPyDialogueModule 資源清理完成")
        except Exception as e:
            logger.error(f"資源清理錯誤: {e}")

# 便利函數
def create_dialogue_module(config: Optional[Dict[str, Any]] = None) -> DSPyDialogueModule:
    """創建 DSPy 對話模組
    
    Args:
        config: 配置字典
        
    Returns:
        配置好的 DSPyDialogueModule
    """
    try:
        return DSPyDialogueModule(config)
    except Exception as e:
        logger.error(f"創建對話模組失敗: {e}")
        raise

# 測試函數
def test_dialogue_module():
    """測試 DSPy 對話模組"""
    print("🧪 測試 DSPy 對話模組...")
    
    try:
        # 創建模組
        print("\n1. 創建對話模組:")
        module = DSPyDialogueModule()
        print("  ✅ 模組創建成功")
        
        # 測試對話處理
        print("\n2. 測試對話處理:")
        test_input = "你今天感覺如何？"
        
        try:
            result = module(
                user_input=test_input,
                character_name="測試病患",
                character_persona="友善但有些擔心的病患",
                character_backstory="住院中的老人",
                character_goal="康復出院",
                character_details="",
                conversation_history=[]
            )
            
            print(f"  ✅ 對話處理成功")
            print(f"    用戶輸入: {test_input}")
            print(f"    回應數量: {len(result.responses)}")
            print(f"    對話狀態: {result.state}")
            print(f"    情境分類: {result.dialogue_context}")
            
            # 顯示回應
            for i, response in enumerate(result.responses, 1):
                print(f"    回應{i}: {response[:50]}...")
                
        except Exception as e:
            print(f"  ❌ 對話處理失敗: {e}")
        
        # 測試統計功能
        print("\n3. 統計資訊:")
        stats = module.get_statistics()
        print(f"  總調用次數: {stats['total_calls']}")
        print(f"  成功率: {stats['success_rate']:.2%}")
        
        # 清理資源
        print("\n4. 清理資源:")
        module.cleanup()
        print("  ✅ 資源清理完成")
        
        print("\n✅ DSPy 對話模組測試完成")
        return True
        
    except Exception as e:
        print(f"❌ 對話模組測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_dialogue_module()
