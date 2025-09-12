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
    """統一的病患回應生成簽名 - 智能上下文管理版本
    
    將情境分類、回應生成、狀態判斷合併為單一調用，
    減少 API 使用次數從 3次 降低到 1次。
    
    核心原則：
    1. 以已建立的病患角色自然回應
    2. 避免不必要的自我介紹
    3. 保持角色一致性和對話流暢度
    """
    
    # 輸入欄位 - 護理人員和對話相關信息
    user_input = dspy.InputField(desc="護理人員的輸入或問題")
    character_name = dspy.InputField(desc="病患角色的名稱")
    character_persona = dspy.InputField(desc="病患的個性描述")
    character_backstory = dspy.InputField(desc="病患的背景故事")
    character_goal = dspy.InputField(desc="病患的目標")
    character_details = dspy.InputField(desc="病患的詳細設定，包含固定和浮動設定的YAML格式字符串")
    conversation_history = dspy.InputField(desc="最近的對話歷史，以換行分隔，包含角色一致性提醒")
    available_contexts = dspy.InputField(desc="可用的對話情境列表")
    
    # 輸出欄位 - 統一的回應結果  
    reasoning = dspy.OutputField(desc="推理過程：包含情境分析、角色一致性檢查、回應思考和狀態評估。必須確認不會進行自我介紹。")
    character_consistency_check = dspy.OutputField(desc="角色一致性檢查：確認回應符合已建立的角色人格，不包含自我介紹。回答 YES 或 NO")
    context_classification = dspy.OutputField(desc="對話情境分類：vital_signs_examples, daily_routine_examples, treatment_examples 等")
    confidence = dspy.OutputField(desc="情境分類的信心度，0.0到1.0之間")
    responses = dspy.OutputField(desc="5個不同的病患回應選項，每個都應該是完整的句子，格式為JSON陣列。以已建立的病患角色身份自然回應，避免自我介紹。")
    state = dspy.OutputField(desc="對話狀態：必須是 NORMAL、CONFUSED、TRANSITIONING 或 TERMINATED 其中之一。只有在真正無法理解時才使用 CONFUSED")
    dialogue_context = dspy.OutputField(desc="當前對話情境描述，如：醫師查房、病房日常、生命徵象相關、身體評估等。保持具體的醫療情境描述")
    state_reasoning = dspy.OutputField(desc="狀態判斷的理由說明，解釋為什麼選擇此狀態")


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
            
            # 改善對話歷史管理 - 確保角色一致性
            formatted_history = self._get_enhanced_conversation_history(
                conversation_history, character_name, character_persona
            )
            
            # 獲取可用情境（本地處理，不調用 API）
            available_contexts = self._get_available_contexts()
            
            # ====== 詳細調試日誌 - 追蹤對話退化問題 ======
            logger.info(f"=== UNIFIED DSPy CALL #{self.unified_stats['total_unified_calls'] + 1} (節省 2次 API 調用) ===")
            logger.info(f"🔍 DIALOGUE DEGRADATION DEBUG:")
            logger.info(f"  📥 Input: {user_input}")
            logger.info(f"  👤 Character: {character_name} ({character_persona})")
            logger.info(f"  📚 Full conversation history ({len(conversation_history)} total):")
            for i, hist_item in enumerate(conversation_history, 1):
                logger.info(f"    [{i:2}] {hist_item}")
            logger.info(f"  📝 Formatted history (last 5): {formatted_history}")
            logger.info(f"  🎯 Available contexts: {available_contexts}")
            logger.info(f"  📊 Stats - Total calls: {self.stats.get('total_calls', 0)}, Success: {self.stats.get('successful_calls', 0)}")
            logger.info(f"=== 開始單次調用處理：情境分類 + 回應生成 + 狀態判斷 ===")
            
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
            
            # ====== 詳細推理結果日誌 - 診斷退化原因 ======
            logger.info(f"=== UNIFIED DSPy RESULT - DEGRADATION ANALYSIS ===")
            logger.info(f"🧠 DSPy REASONING OUTPUT:")
            logger.info(f"  💭 reasoning: {getattr(unified_prediction, 'reasoning', 'NOT_PROVIDED')}")
            logger.info(f"  ✅ character_consistency_check: {getattr(unified_prediction, 'character_consistency_check', 'NOT_PROVIDED')}")
            logger.info(f"  🎯 context_classification: {unified_prediction.context_classification}")
            logger.info(f"  🎪 confidence: {unified_prediction.confidence}")
            logger.info(f"  📊 state: {unified_prediction.state}")
            logger.info(f"  🌍 dialogue_context: {unified_prediction.dialogue_context}")
            logger.info(f"  🔍 state_reasoning: {getattr(unified_prediction, 'state_reasoning', 'NOT_PROVIDED')}")
            
            # 解析並顯示回應內容
            parsed_responses = self._parse_responses(unified_prediction.responses)
            logger.info(f"  💬 responses ({len(parsed_responses)}):")
            for i, response in enumerate(parsed_responses, 1):
                logger.info(f"    [{i}] {response}")
            
            # 關鍵診斷：檢查是否出現退化症狀
            is_degraded = self._detect_dialogue_degradation(unified_prediction, parsed_responses)
            logger.info(f"  ⚠️  DEGRADATION DETECTED: {is_degraded}")
            if is_degraded:
                logger.warning(f"🚨 DIALOGUE DEGRADATION WARNING - Response quality has declined!")
            
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
    
    def _detect_dialogue_degradation(self, prediction, responses: List[str]) -> bool:
        """檢測對話是否出現退化症狀
        
        Args:
            prediction: DSPy prediction 結果
            responses: 解析後的回應列表
            
        Returns:
            bool: True 如果檢測到退化症狀
        """
        degradation_indicators = []
        
        # 檢查1: 是否出現自我介紹模式
        self_introduction_pattern = False
        for response in responses:
            if any(pattern in response for pattern in ["我是Patient", "您好，我是", "我是病患", "我是{}"]):
                self_introduction_pattern = True
                degradation_indicators.append("self_introduction")
                break
        
        # 檢查2: 是否狀態為 CONFUSED
        if getattr(prediction, 'state', '') == 'CONFUSED':
            degradation_indicators.append("confused_state")
        
        # 檢查3: 是否回應質量下降（通用回應）
        generic_responses = ["我可能沒有完全理解", "能請您換個方式說明", "您需要什麼幫助嗎"]
        generic_pattern = any(
            any(generic in response for generic in generic_responses)
            for response in responses
        )
        if generic_pattern:
            degradation_indicators.append("generic_responses")
        
        # 檢查4: 是否信心度過低
        confidence = getattr(prediction, 'confidence', 1.0)
        try:
            confidence_float = float(confidence) if confidence else 1.0
            if confidence_float < 0.5:
                degradation_indicators.append("low_confidence")
        except (ValueError, TypeError):
            pass
        
        # 記錄具體的退化指標
        if degradation_indicators:
            logger.warning(f"🚨 Degradation indicators detected: {', '.join(degradation_indicators)}")
            logger.warning(f"   Self-introduction: {self_introduction_pattern}")
            logger.warning(f"   State: {getattr(prediction, 'state', 'UNKNOWN')}")
            logger.warning(f"   Confidence: {confidence}")
            logger.warning(f"   Generic patterns: {generic_pattern}")
        
        return len(degradation_indicators) > 0
    
    def _get_enhanced_conversation_history(self, conversation_history: List[str], 
                                         character_name: str, character_persona: str) -> str:
        """獲取增強的對話歷史，保持角色一致性
        
        Args:
            conversation_history: 完整對話歷史
            character_name: 角色名稱
            character_persona: 角色個性
            
        Returns:
            str: 格式化後的對話歷史
        """
        if not conversation_history:
            return ""
        
        max_history = 8  # 增加到8輪以提供更多上下文
        
        if len(conversation_history) <= max_history:
            formatted = "\n".join(conversation_history)
        else:
            # 策略：保留前3輪（角色建立期）+ 最近5輪（當前對話）
            important_start = conversation_history[:6]  # 前3輪對話（護理人員+病患各3次）
            recent = conversation_history[-(max_history-3):]  # 最近5輪
            
            # 避免重複
            if len(conversation_history) > max_history:
                combined = important_start + recent
                # 去除重複項（如果有）
                seen = set()
                unique_history = []
                for item in combined:
                    if item not in seen:
                        unique_history.append(item)
                        seen.add(item)
                formatted = "\n".join(unique_history[-max_history:])
            else:
                formatted = "\n".join(conversation_history)
        
        # 使用智能上下文重置機制 - 當對話可能造成混亂時重置上下文
        should_reset_context = self._should_reset_conversation_context(conversation_history)
        
        if should_reset_context:
            # 重置為基本角色設定，保留關鍵醫療信息
            formatted = self._create_reset_context(character_name, character_persona)
            character_reminder = f"\n[重新開始: 您是 {character_name}，{character_persona}。以病患身份自然回應。]"
            logger.info(f"🔄 Context reset triggered to prevent degradation")
        else:
            # 正常的角色一致性提示
            character_reminder = f"\n[重要: 您是 {character_name}，{character_persona}。保持角色一致性。]"
        
        logger.info(f"🔧 Enhanced history management:")
        logger.info(f"  Original history length: {len(conversation_history)}")
        logger.info(f"  Enhanced history length: {len(formatted.split())}")
        logger.info(f"  Character reminder added: {character_name}")
        logger.info(f"  Context reset applied: {should_reset_context}")
        
        return formatted + character_reminder
    
    def _should_reset_conversation_context(self, conversation_history: List[str]) -> bool:
        """決定是否需要重置對話上下文以防止退化"""
        if not conversation_history or len(conversation_history) < 6:
            return False
        
        # 檢查是否有重複的護理人員輸入（可能導致混亂）
        user_inputs = [entry for entry in conversation_history if entry.startswith("護理人員: ")]
        if len(user_inputs) >= 2:
            # 檢查最後兩個輸入是否相同
            if user_inputs[-1] == user_inputs[-2]:
                return True
        
        # 檢查是否已經超過 6 輪對話（DSPy 容易在長對話中退化）
        if len(conversation_history) > 12:  # 6輪對話 = 12個條目（護理人員+病患各6次）
            return True
        
        # 檢查最近的病患回應是否包含退化指標
        patient_responses = [entry for entry in conversation_history if not entry.startswith("護理人員: ")]
        if patient_responses:
            recent_response = patient_responses[-1]
            degradation_patterns = ["我是Patient", "您需要什麼幫助", "沒有完全理解"]
            if any(pattern in recent_response for pattern in degradation_patterns):
                return True
        
        return False
    
    def _create_reset_context(self, character_name: str, character_persona: str) -> str:
        """創建重置的對話上下文，保留核心角色信息"""
        reset_context = f"""最近的醫療狀況：
{character_name} 是一位 {character_persona}
正在接受護理人員的照護
目前狀況穩定，正在康復中"""
        
        return reset_context
    
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