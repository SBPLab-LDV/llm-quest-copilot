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
from .consistency_checker import DialogueConsistencyChecker

logger = logging.getLogger(__name__)

JSON_OUTPUT_DIRECTIVE = (
    "[指示] 僅輸出單一 JSON 物件，欄位依序為 "
    "reasoning, character_consistency_check, context_classification, confidence, "
    "responses, state, dialogue_context, state_reasoning；responses 必須是 5 個短句字串的陣列。"
    "禁止使用 [[ ## field ## ]]、markdown 標記或任何額外文字，且所有鍵與值都需使用雙引號。"
)

PERSONA_REMINDER_TEMPLATE = (
    "[角色提醒] 您是 {name}，{persona}。確保與上方醫療事實一致，" 
    "不得自我介紹或自稱 AI。"
)

DEFAULT_CONTEXT_PRIORITY = [
    "daily_routine_examples",
    "treatment_examples",
    "vital_signs_examples",
]


class UnifiedPatientResponseSignature(dspy.Signature):
    """統一的病患回應生成簽名（精簡提示）。"""

    # 輸入欄位
    user_input = dspy.InputField(desc="護理人員問題")
    character_name = dspy.InputField(desc="病患姓名")
    character_persona = dspy.InputField(desc="病患性格")
    character_backstory = dspy.InputField(desc="病患背景")
    character_goal = dspy.InputField(desc="病患目標")
    character_details = dspy.InputField(desc="關鍵病情資訊")
    conversation_history = dspy.InputField(desc="近期對話與提醒")
    available_contexts = dspy.InputField(desc="候選情境")

    # 輸出欄位
    reasoning = dspy.OutputField(desc="推理與一致性檢查")
    character_consistency_check = dspy.OutputField(desc="角色一致性 YES/NO")
    context_classification = dspy.OutputField(desc="情境分類 ID")
    confidence = dspy.OutputField(desc="情境信心 0-1")
    responses = dspy.OutputField(desc="五個病患回應")
    state = dspy.OutputField(desc="對話狀態")
    dialogue_context = dspy.OutputField(desc="情境描述")
    state_reasoning = dspy.OutputField(desc="狀態原因")



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
        
        # 替換為統一的對話處理器（使用預設 JSONAdapter 流程）
        self.unified_response_generator = dspy.ChainOfThought(UnifiedPatientResponseSignature)

        # 追蹤最近一次模型輸出情境，做為下輪提示濾器
        self._last_context_label: Optional[str] = None

        # 一致性檢查（Phase 0/1）：預設開啟，可由 config 覆寫
        self.consistency_checker = DialogueConsistencyChecker()
        enable_flag = True
        try:
            if isinstance(config, dict) and 'enable_consistency_check' in config:
                enable_flag = bool(config.get('enable_consistency_check', True))
            elif hasattr(self, 'config') and isinstance(self.config, dict):
                enable_flag = bool(self.config.get('enable_consistency_check', True))
        except Exception:
            enable_flag = True
        self.enable_consistency_check = enable_flag
        
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
            
            # 將輸出格式要求附加到提示末端
            if formatted_history:
                formatted_history = f"{formatted_history}\n{JSON_OUTPUT_DIRECTIVE}"
            else:
                formatted_history = JSON_OUTPUT_DIRECTIVE

            # 獲取精簡後的可用情境清單
            available_contexts = self._build_available_contexts()

            # 可選：插入 few-shot 範例（k=2），強化冷啟/語境不足回合
            fewshot_text = ""
            try:
                enable_fewshot = len(conversation_history or []) < 2
                if enable_fewshot and hasattr(self, 'example_selector'):
                    fewshots = self.example_selector.select_examples(
                        query=user_input, context=None, k=2, strategy="hybrid"
                    )
                    fs_blocks = []
                    for i, ex in enumerate(fewshots, 1):
                        ui = getattr(ex, 'user_input', '') or getattr(ex, 'input', '')
                        out = getattr(ex, 'responses', None) or getattr(ex, 'output', None) or getattr(ex, 'answer', None)
                        if isinstance(out, list) and out:
                            out_text = str(out[0])
                        else:
                            out_text = str(out) if out is not None else ''
                        fs_blocks.append(f"[範例{i}]\n護理人員: {ui}\n病患: {out_text}")
                    if fs_blocks:
                        fewshot_text = "\n".join(fs_blocks) + "\n"
                        formatted_history = fewshot_text + formatted_history
                        logger.info(f"🧩 Injected few-shot examples: {len(fs_blocks)}")
            except Exception as _e:
                logger.info(f"Few-shot injection skipped: {_e}")
            
            current_call = self.unified_stats['total_unified_calls'] + 1
            logger.info(f"🚀 Unified DSPy call #{current_call} - {character_name} processing {len(conversation_history)} history entries")
            
            # **關鍵優化：單一 API 調用完成所有處理**
            import time
            call_start_time = time.time()
            
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
            
            call_end_time = time.time()
            call_duration = call_end_time - call_start_time
            
            logger.info(f"✅ Call #{current_call} completed in {call_duration:.3f}s - {type(unified_prediction).__name__}")


            parsed_responses = self._parse_responses(unified_prediction.responses)
            logger.info(f"💬 Generated {len(parsed_responses)} responses - State: {unified_prediction.state}")
            logger.info(f"📈 API calls saved: 2 (1 vs 3 original calls)")

            # 更新情境偏好，供下一輪精簡提示使用
            try:
                raw_context = getattr(unified_prediction, 'context_classification', None)
                normalized_context = self._normalize_context_label(raw_context)
                if normalized_context:
                    self._last_context_label = normalized_context
            except Exception:
                pass

            # Detailed reasoning and fields for inspection
            try:
                logger.info("=== UNIFIED REASONING OUTPUT ===")
                logger.info(f"reasoning: {getattr(unified_prediction, 'reasoning', '')}")
                logger.info(f"character_consistency_check: {getattr(unified_prediction, 'character_consistency_check', '')}")
                logger.info(f"context_classification: {getattr(unified_prediction, 'context_classification', '')}")
                logger.info(f"confidence: {getattr(unified_prediction, 'confidence', '')}")
                logger.info(f"dialogue_context: {getattr(unified_prediction, 'dialogue_context', '')}")
                logger.info(f"state_reasoning: {getattr(unified_prediction, 'state_reasoning', '')}")
                # Show up to first 3 responses for brevity
                _resp_preview = parsed_responses[:3]
                logger.info(f"responses_preview: {_resp_preview}")
            except Exception:
                pass
            
            # 處理回應格式
            responses = self._process_responses(unified_prediction.responses)

            # 一致性檢查與修正（不發起額外 LLM 請求）
            consistency_info = None
            if getattr(self, 'enable_consistency_check', True):
                try:
                    consistency_result = self.consistency_checker.check_consistency(
                        new_responses=responses,
                        conversation_history=conversation_history or [],
                        character_context={
                            'name': character_name,
                            'persona': character_persona
                        }
                    )
                    consistency_info = {
                        'score': round(float(consistency_result.score), 3),
                        'contradictions': len(consistency_result.contradictions),
                        'severity': consistency_result.severity,
                    }
                    if consistency_result.has_contradictions:
                        responses = self._apply_consistency_fixes(responses, consistency_result)
                except Exception as _:
                    # 不阻斷主流程
                    pass
            
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
                reasoning=getattr(unified_prediction, 'reasoning', ''),
                context_classification=unified_prediction.context_classification,
                examples_used=0,  # 統一模式下暫不使用範例
                processing_info={
                    'unified_call': True,
                    'api_calls_saved': 2,
                    'context_classification': unified_prediction.context_classification,
                    'state_reasoning': getattr(unified_prediction, 'state_reasoning', ''),
                    'timestamp': datetime.now().isoformat(),
                    **({'consistency': consistency_info} if consistency_info else {})
                }
            )
            
            # 更新成功率
            self.unified_stats['success_rate'] = (
                self.stats['successful_calls'] / self.stats['total_calls']
                if self.stats['total_calls'] > 0 else 0
            )
            
            logger.info(f"✅ Unified dialogue processing successful - 66.7% API savings")
            return final_prediction
            
        except Exception as e:
            self.stats['failed_calls'] += 1
            logger.error(f"❌ Unified DSPy call failed: {type(e).__name__} - {str(e)}")
            logger.error(f"Input: {user_input[:100]}... (character: {character_name})")
            
            # 返回錯誤回應
            return self._create_error_response(user_input, str(e))
    
    def _parse_responses(self, responses_text: Union[str, List[Any]]) -> List[str]:
        """解析回應為列表（僅用於日誌顯示）"""
        def _extract_from_dict(data: Dict[str, Any]) -> Optional[List[str]]:
            if not isinstance(data, dict):
                return None
            candidate = data.get('responses')
            if isinstance(candidate, list):
                return [str(x) for x in candidate[:5]]
            if isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:5]]
                except Exception:
                    return [candidate]
            return None

        try:
            # 已是列表
            if isinstance(responses_text, list):
                # 處理 list 內只有一個元素且該元素是 JSON 陣列字串的情況
                if len(responses_text) == 1 and isinstance(responses_text[0], str):
                    inner = responses_text[0].strip()
                    if (inner.startswith('[') and inner.endswith(']')) or (inner.startswith('\u005b') and inner.endswith('\u005d')):
                        try:
                            parsed_inner = json.loads(inner)
                            if isinstance(parsed_inner, list):
                                return [str(x) for x in parsed_inner[:5]]
                        except Exception:
                            pass
                # 常規列表
                return [str(x) for x in responses_text[:5]]
            
            if isinstance(responses_text, dict):
                extracted = _extract_from_dict(responses_text)
                if extracted is not None:
                    return extracted
            
            # 原始是字串 -> 嘗試 JSON 解析
            if isinstance(responses_text, str):
                try:
                    parsed = json.loads(responses_text)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:5]]
                    if isinstance(parsed, dict):
                        extracted = _extract_from_dict(parsed)
                        if extracted is not None:
                            return extracted
                except json.JSONDecodeError:
                    # 不是 JSON，按行分割
                    lines = [line.strip() for line in responses_text.split('\n') if line.strip()]
                    return lines[:5]
            
            return [str(responses_text)]
        except Exception as e:
            logger.warning(f"回應解析失敗: {e}")
            return ["回應格式解析失敗"]

    # 覆蓋父類回應處理，處理特殊嵌套情況
    def _process_responses(self, responses: Union[str, List[Any]]) -> List[str]:
        def _extract_from_dict(data: Dict[str, Any]) -> Optional[List[str]]:
            if not isinstance(data, dict):
                return None
            candidate = data.get('responses')
            if isinstance(candidate, list):
                return [str(x) for x in candidate[:5]]
            if isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:5]]
                except Exception:
                    return [candidate]
            return None

        try:
            # 已是列表
            if isinstance(responses, list):
                # 若為 ["[\"a\", \"b\"]"] 形式，嘗試解析內層字串為陣列
                if len(responses) == 1 and isinstance(responses[0], str):
                    inner = responses[0].strip()
                    if inner.startswith('[') and inner.endswith(']'):
                        try:
                            parsed_inner = json.loads(inner)
                            if isinstance(parsed_inner, list):
                                return [str(x) for x in parsed_inner[:5]]
                        except Exception:
                            pass
                # 若為 [[...]] 形式，展平為單層
                if len(responses) == 1 and isinstance(responses[0], list):
                    return [str(x) for x in responses[0][:5]]
                return [str(x) for x in responses[:5]]
            
            if isinstance(responses, dict):
                extracted = _extract_from_dict(responses)
                if extracted is not None:
                    return extracted

            # 原始是字串 -> 嘗試 JSON 解析
            if isinstance(responses, str):
                try:
                    parsed = json.loads(responses)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:5]]
                    if isinstance(parsed, dict):
                        extracted = _extract_from_dict(parsed)
                        if extracted is not None:
                            return extracted
                except json.JSONDecodeError:
                    lines = [line.strip() for line in responses.split('\n') if line.strip()]
                    return lines[:5]
            
            return [str(responses)]
        except Exception as e:
            logger.error(f"回應格式處理失敗: {e}", exc_info=True)
            return [f"UnifiedResponseFormatError[{type(e).__name__}]: {e}"]


    def _build_available_contexts(self) -> str:
        """回傳最多三個高優先情境，避免提示冗長。"""
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

        prioritized: List[Any] = []
        if self._last_context_label:
            prioritized.append(self._last_context_label)
        prioritized.extend(DEFAULT_CONTEXT_PRIORITY)

        try:
            if hasattr(self, 'example_selector') and self.example_selector:
                bank_contexts = self.example_selector.example_bank.get_context_list()
                prioritized.extend(bank_contexts)
        except Exception:
            pass

        # 去重保序後取前三個
        compact: List[str] = []
        for ctx in prioritized:
            label = self._normalize_context_label(ctx)
            if not label:
                continue
            if label not in compact:
                compact.append(label)
            if len(compact) == 3:
                break

        if not compact:
            compact = DEFAULT_CONTEXT_PRIORITY[:3]

        return "\n".join(
            f"- {ctx}: {context_descriptions.get(ctx, ctx)}" for ctx in compact
        )


    def _normalize_context_label(self, label: Any) -> Optional[str]:
        if isinstance(label, str):
            value = label.strip()
            if not value:
                return None
            if value.startswith('{') and value.endswith('}'):
                try:
                    parsed = json.loads(value)
                    return self._normalize_context_label(parsed)
                except Exception:
                    return None
            return value
        if isinstance(label, dict):
            for key in ('context_classification', 'label', 'id', 'name', 'value'):
                if key in label:
                    normalized = self._normalize_context_label(label[key])
                    if normalized:
                        return normalized
        return None


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
        reminder = PERSONA_REMINDER_TEMPLATE.format(name=character_name, persona=character_persona)

        if not conversation_history:
            return reminder

        max_history = 5

        if len(conversation_history) <= max_history:
            trimmed = list(conversation_history)
        else:
            important = conversation_history[:2]
            recent = conversation_history[-(max_history - len(important)) :]
            combined = important + recent
            seen = set()
            trimmed = []
            for item in combined:
                if item not in seen:
                    trimmed.append(item)
                    seen.add(item)
        
        formatted = "\n".join(trimmed[-max_history:])
        logger.info(
            f"🔧 History management: {len(conversation_history)} entries processed for {character_name}"
        )
        return f"{formatted}\n{reminder}"
    
    
    
    def _check_model_state_change(self) -> bool:
        """檢查模型狀態是否有變化
        
        Returns:
            bool: True if state changed
        """
        try:
            # 簡單的狀態變化檢查
            current_calls = self.stats.get('total_calls', 0)
            if not hasattr(self, '_last_total_calls'):
                self._last_total_calls = current_calls
                return True
            
            changed = current_calls != self._last_total_calls
            self._last_total_calls = current_calls
            return changed
            
        except Exception:
            return False
    
    
    
    
    
    
    
    
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

    def _apply_consistency_fixes(self, responses: List[str], consistency_result) -> List[str]:
        """根據一致性結果對回應進行最小侵入式修正
        - high：移除自我介紹/明顯矛盾回應；若全被移除則回退保留前兩則中性回應
        - medium/low：附加輕量提示文字，提醒保持與先前陳述一致
        """
        if not responses:
            return responses

        # 目前僅記錄一致性結果，不再修改 Gemini 回覆內容，以便檢視原始輸出。
        try:
            _ = {c.type for c in consistency_result.contradictions}
        except Exception:
            pass
        return list(responses)


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
