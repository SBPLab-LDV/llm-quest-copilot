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


class UnifiedPatientResponseSignature(dspy.Signature):
    """統一的病患回應生成簽名 - JSON 輸出版本
    
    將情境分類、回應生成、狀態判斷合併為單一調用，
    減少 API 使用次數從 3 次降至 1 次。
    
    【輸出格式要求 - 重要】
    - 僅輸出「單一有效 JSON 物件」，不允許任何額外文字或 markdown 代碼塊（如 ``` 或 ```json）。
    - 必須包含且只包含以下鍵（鍵名需精確匹配）：
      reasoning, character_consistency_check, context_classification, confidence,
      responses, state, dialogue_context, state_reasoning。
    - responses 必須是字串陣列（5 個不同、自然的句子）。
    - confidence 使用字串型態的數值（如 "0.90"，範圍 0.80–0.98）。
    - state 僅在「完全無法辨識或毫無語義」時才可為 CONFUSED；一般情況請輸出 NORMAL。
    - 若生成過程中發現缺少任何必填鍵或格式錯誤，請自行修正並重新輸出完整 JSON（不要輸出中間稿）。
    
    【正確 JSON 範例】
    {
      "reasoning": "詳細推理過程...",
      "character_consistency_check": "YES",
      "context_classification": "daily_routine_examples",
      "confidence": "0.90",
      "responses": ["回應1", "回應2", "回應3", "回應4", "回應5"],
      "state": "NORMAL",
      "dialogue_context": "病房日常對話",
      "state_reasoning": "選擇 NORMAL 的原因說明"
    }
    
    【禁止事項】
    - 不要輸出 field header（如 [[ ## field ## ]]）。
    - 不要輸出任何多餘的說明或標記（僅允許 JSON 物件）。
    - 不要使用單引號包裹鍵或值（必須是雙引號）。
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
    reasoning = dspy.OutputField(desc="推理過程：包含情境分析、角色一致性檢查、回應思考和狀態評估。必須確認不會進行自我介紹。【重要】邏輯一致性檢查：1) 仔細檢視對話歷史中的所有事實陳述（症狀、時間、治療狀況等）；2) 確認新回應不會與之前提到的任何醫療事實產生矛盾；3) 特別注意症狀描述、疼痛程度、發燒狀況、服藥情形等細節的前後一致性；4) 如發現潛在矛盾，必須調整回應以維持邏輯一致性；5) 明確說明檢查結果和調整內容。")
    character_consistency_check = dspy.OutputField(desc="角色一致性檢查：確認回應符合已建立的角色人格，不包含自我介紹。回答 YES 或 NO")
    context_classification = dspy.OutputField(desc="對話情境分類：vital_signs_examples, daily_routine_examples, treatment_examples 等")
    confidence = dspy.OutputField(desc="情境分類的信心度，0.0到1.0之間")
    responses = dspy.OutputField(desc="5個不同的病患回應選項，每個都應該是完整的句子，格式為字串陣列。以已建立的病患角色身份自然回應，避免自我介紹。【格式要求】必須是有效的字串陣列格式，例如：[\"回應1\", \"回應2\", \"回應3\", \"回應4\", \"回應5\"]")
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
        
        # 替換為統一的對話處理器（使用預設 JSONAdapter 流程）
        self.unified_response_generator = dspy.ChainOfThought(UnifiedPatientResponseSignature)

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
            
            # 獲取可用情境（本地處理，不調用 API）
            available_contexts = self._get_available_contexts()

            # 可選：插入 few-shot 範例（k=2），強化冷啟/語境不足回合
            fewshot_text = ""
            try:
                enable_fewshot = True if isinstance(self.config, dict) else True
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
            
            # 原始是字串 -> 嘗試 JSON 解析
            if isinstance(responses_text, str):
                try:
                    parsed = json.loads(responses_text)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:5]]
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
            
            # 原始是字串 -> 嘗試 JSON 解析
            if isinstance(responses, str):
                try:
                    parsed = json.loads(responses)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:5]]
                except json.JSONDecodeError:
                    lines = [line.strip() for line in responses.split('\n') if line.strip()]
                    return lines[:5]
            
            return [str(responses)]
        except Exception as e:
            logger.error(f"回應格式處理失敗: {e}")
            return ["抱歉，我現在有些困惑", "能否重新說一遍？", "讓我想想..."]
    
    
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
        
        # 添加角色一致性提示和邏輯一致性檢查
        character_reminder = f"\n[重要: 您是 {character_name}，{character_persona}。保持角色一致性。【邏輯一致性檢查】請仔細檢查上述對話歷史中的醫療事實（症狀、發燒狀況、疼痛程度、服藥情況等），確保您的回應與之前提到的所有事實保持完全一致，避免任何矛盾。]"
        
        logger.info(f"🔧 History management: {len(conversation_history)} entries processed for {character_name}")
        
        return formatted + character_reminder
    
    
    
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

        fixed = list(responses)

        try:
            # 判定類型集合
            types = {c.type for c in consistency_result.contradictions}

            # high 等級：過濾自我介紹與過度通用回應
            if consistency_result.severity == 'high':
                fixed = [r for r in fixed if all(k not in str(r) for k in ["我是Patient", "您好，我是", "我是"])]
                fixed = [r for r in fixed if all(k not in str(r) for k in ["我可能沒有完全理解", "您需要什麼幫助"])]
                # 若全被清空，提供安全的中性回應，避免回灌原始矛盾內容
                if not fixed:
                    fixed = [
                        "還可以，傷口有點緊繃。",
                        "目前狀況還算穩定。",
                        "偶爾會覺得有點不舒服。"
                    ]

            # medium/low：加提示尾註，避免破壞原意
            else:
                hint = "（保持與先前陳述一致）"
                fixed = [r if hint in str(r) else f"{r}{hint}" for r in fixed]

            # 最多保留 5 則
            return fixed[:5]
        except Exception:
            return responses


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
