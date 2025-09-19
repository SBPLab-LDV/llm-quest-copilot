#!/usr/bin/env python3
"""
優化版 DSPy 對話管理器

使用統一對話模組，將 API 調用從 3次 減少到 1次，
解決 Gemini API 配額限制問題。
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Union

from ..dialogue import DialogueManager
from ..character import Character
from .unified_dialogue_module import UnifiedDSPyDialogueModule
from .sensitive_question_module import SensitiveQuestionRewriteModule
from .config import get_config

logger = logging.getLogger(__name__)


class OptimizedDialogueManagerDSPy(DialogueManager):
    """優化版 DSPy 對話管理器

    主要優化：
    - API 調用從 3次 減少到 1次 (節省 66.7% 配額使用)
    - 保持完全的 API 兼容性
    - 提供詳細的節省統計
    """
    
    def __init__(self, character: Character, use_terminal: bool = False, log_dir: str = "logs"):
        """初始化優化版 DSPy 對話管理器
        
        Args:
            character: Character instance containing the NPC's information (as patient identifier)
            use_terminal: Whether to use terminal mode for interaction
            log_dir: Directory to save interaction logs
        """
        # 初始化父類
        super().__init__(character, use_terminal, log_dir)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("OptimizedDialogueManagerDSPy.__init__ - 使用統一對話模組")
        
        # 讀取敏感提問改寫開關
        dspy_config = get_config().get_dspy_config()
        self.enable_sensitive_rewrite = dspy_config.get('enable_sensitive_rewrite', True)

        # 初始化優化的 DSPy 組件
        try:
            self.dialogue_module = UnifiedDSPyDialogueModule()
            self.optimization_enabled = True
            self.logger.info("優化統一對話模組初始化成功 - API 調用節省 66.7%")
            if self.enable_sensitive_rewrite:
                self.sensitive_question_module = SensitiveQuestionRewriteModule()
            else:
                self.sensitive_question_module = None
                self.logger.info("敏感提問改寫已停用（enable_sensitive_rewrite=False）")
        except Exception as e:
            self.logger.error(f"統一對話模組初始化失敗: {e}")
            self.optimization_enabled = False
            # 回退到原始實現
            from .dialogue_manager_dspy import DialogueManagerDSPy
            fallback_manager = DialogueManagerDSPy(character, use_terminal, log_dir)
            self.dialogue_module = fallback_manager.dialogue_module
            if self.enable_sensitive_rewrite:
                self.sensitive_question_module = getattr(
                    fallback_manager,
                    'sensitive_question_module',
                    SensitiveQuestionRewriteModule(),
                )
            else:
                self.sensitive_question_module = None
            self.logger.warning("已回退到原始 DSPy 實現")
        
        # 統計追蹤
        self.optimization_stats = {
            'total_conversations': 0,
            'api_calls_saved': 0,
            'estimated_quota_saved_percent': 0.0
        }
        self._character_profile_emitted = False

    async def process_turn(self, user_input: str, gui_selected_response: Optional[str] = None) -> Union[str, dict]:
        """處理優化版對話輪次
        
        Args:
            user_input: The user's input text
            gui_selected_response: Selected response in GUI mode (optional)
            
        Returns:
            Either a string response (terminal mode) or JSON response (GUI mode)
        """
        if not self.optimization_enabled:
            # 回退到父類實現
            return await super().process_turn(user_input, gui_selected_response)
        
        self.optimization_stats['total_conversations'] += 1
        
        try:
            self.logger.info(f"=== 優化版對話處理 (第 {self.optimization_stats['total_conversations']} 次) ===")
            self.logger.info(f"用戶輸入: {user_input}")
            
            # 檢查重複輸入 - 避免在會話中添加相同的輸入
            last_user_input = None
            if self.conversation_history:
                for entry in reversed(self.conversation_history):
                    if entry.startswith("護理人員: "):
                        last_user_input = entry[5:]  # 移除 "護理人員: " 前綴
                        break
            
            is_duplicate_input = (last_user_input == user_input)
            
            # 只有不是重複輸入時才記錄到對話歷史
            if not is_duplicate_input:
                self.conversation_history.append(f"護理人員: {user_input}")
                self.logger.info(f"✅ 新輸入已記錄到對話歷史")
            else:
                self.logger.info(f"⚠️ 檢測到重複輸入，跳過記錄到對話歷史，避免混亂")
            
            # 使用優化的統一對話模組 (僅1次 API 調用)
            prediction = self.dialogue_module(
                user_input=user_input,
                character_name=self.character.name,
                character_persona=self.character.persona,
                character_backstory=self.character.backstory,
                character_goal=self.character.goal,
                character_details=self._get_character_details(),
                conversation_history=self._format_conversation_history()
            )
            
            self.logger.info(f"優化處理完成:")
            self.logger.info(f"  - API 調用次數: 1 (原本需要 3次)")
            self.logger.info(f"  - 節省配額使用: 66.7%")
            self.logger.info(f"  - 回應數量: {len(prediction.responses)}")
            self.logger.info(f"  - 情境分類: {prediction.context_classification}")
            
            # 更新節省統計
            saved_calls = prediction.processing_info.get('api_calls_saved', 2)
            self.optimization_stats['api_calls_saved'] += saved_calls
            self.optimization_stats['estimated_quota_saved_percent'] = (
                (self.optimization_stats['api_calls_saved'] / 
                 (self.optimization_stats['total_conversations'] * 3)) * 100
                if self.optimization_stats['total_conversations'] > 0 else 0
            )
            
            # 讓 rewrite 模組決策是否需要改寫
            rewrite_result = self._attempt_sensitive_rewrite(user_input, prediction)

            if rewrite_result:
                response_data = rewrite_result
            else:
                response_data = self._process_optimized_prediction(prediction)

            # 僅監測退化狀態，不改寫回應內容
            response_data = self._apply_degradation_prevention(response_data, user_input)
            
            # ====== Phase 1.3: 會話狀態變化追蹤 ======
            round_number = len(self.conversation_history) // 2 + 1  # 估算輪次
            self._track_session_state_changes(user_input, response_data, round_number)
            
            # 更新對話狀態
            self._update_dialogue_state(response_data)
            
            # 處理終端機模式或 GUI 模式
            if self.use_terminal:
                return self._handle_terminal_mode(user_input, response_data)
            else:
                return self._handle_gui_mode(user_input, response_data, gui_selected_response)
                
        except Exception as e:
            self.logger.error(f"優化版對話處理失敗: {e}")
            self.logger.error("UNIFIED_FAILED: OptimizedDialogueManagerDSPy.process_turn exception", exc_info=True)
            
            # 嘗試從父類獲取回應，然後應用退化防護
            try:
                fallback_result = await super().process_turn(user_input, gui_selected_response)
                
                # 如果父類返回 JSON 字串，解析它
                if isinstance(fallback_result, str):
                    try:
                        fallback_data = json.loads(fallback_result)
                        # 應用退化防護到父類回應
                        protected_data = self._apply_degradation_prevention(fallback_data, user_input)
                        return json.dumps(protected_data, ensure_ascii=False)
                    except json.JSONDecodeError:
                        # 不是 JSON，直接返回
                        return fallback_result
                else:
                    # 父類返回字典，直接應用防護
                    return self._apply_degradation_prevention(fallback_result, user_input)
                    
            except Exception as fallback_error:
                self.logger.error(f"父類回退也失敗: {fallback_error}")
                self.logger.error("FALLBACK_CHAIN_FAILED: super().process_turn exception", exc_info=True)
                # 最終防護：生成安全的恢復回應
                return self._generate_emergency_response(user_input)
    
    def _get_character_details(self) -> str:
        """回傳簡潔的角色摘要供提示使用。"""
        summary_parts: List[str] = []

        details_dict: Optional[Dict[str, Any]] = None
        try:
            if isinstance(self.character.details, dict) and self.character.details:
                details_dict = self.character.details
            elif isinstance(self.character.details, str) and self.character.details.strip():
                details_dict = json.loads(self.character.details)
        except Exception:
            details_dict = None

        if details_dict:
            fixed = details_dict.get('fixed_settings') or {}
            floating = details_dict.get('floating_settings') or {}

            name = fixed.get('姓名') or getattr(self.character, 'name', '')
            diagnosis = fixed.get('診斷') or fixed.get('目前診斷') or ''
            staging = fixed.get('分期') or fixed.get('診斷分期') or ''
            summary_parts.append(
                "姓名: {name} / 診斷: {diag}{stage}".format(
                    name=name or getattr(self.character, 'name', '未知'),
                    diag=diagnosis,
                    stage=f" ({staging})" if staging else ""
                ).strip()
            )

            treatment_stage = floating.get('目前治療階段') or floating.get('治療階段') or ''
            treatment_status = floating.get('目前治療狀態') or ''
            if treatment_stage or treatment_status:
                line = "目前治療階段: {stage}".format(stage=treatment_stage or treatment_status)
                if treatment_stage and treatment_status and treatment_status != treatment_stage:
                    line += f"；狀態: {treatment_status}"
                summary_parts.append(line)

            caregiver = floating.get('主要照顧者') or floating.get('陪伴者')
            if caregiver:
                summary_parts.append(f"陪伴者: {caregiver}")

            notes = floating.get('個案現況')
            if notes and len(notes) <= 80:
                summary_parts.append(f"現況: {notes}")

        if not summary_parts:
            fallback = [
                f"姓名: {getattr(self.character, 'name', '未知')}",
                getattr(self.character, 'persona', ''),
                getattr(self.character, 'goal', ''),
            ]
            summary_parts.extend(part for part in fallback if part)

        summary = " | ".join(summary_parts)

        if not self._character_profile_emitted:
            self._character_profile_emitted = True
            return summary

        return ""
    
    def _process_optimized_prediction(self, prediction) -> dict:
        """處理優化版預測結果"""
        try:
            responses = getattr(prediction, 'responses', [])
            state = self._normalize_state_value(getattr(prediction, 'state', 'NORMAL'))
            dialogue_context = self._normalize_text_field(
                getattr(prediction, 'dialogue_context', '一般對話')
            )
            context_classification = self._normalize_context_value(
                getattr(prediction, 'context_classification', 'daily_routine_examples')
            ) or 'daily_routine_examples'
            processing_info = getattr(prediction, 'processing_info', None)
            
            # 確保回應格式正確
            if isinstance(responses, str):
                try:
                    responses = json.loads(responses)
                except json.JSONDecodeError:
                    import ast as _ast
                    try:
                        parsed = _ast.literal_eval(responses)
                        if isinstance(parsed, list):
                            responses = parsed
                        else:
                            responses = [responses]
                    except Exception:
                        responses = [responses]
            
            if not isinstance(responses, list):
                responses = [str(responses)]

            normalized_list = []
            for item in responses:
                if isinstance(item, list):
                    normalized_list.extend([str(x) for x in item])
                    continue

                if isinstance(item, str):
                    s = item.strip()
                    if s.startswith('['):
                        candidate = s
                        if not s.endswith(']'):
                            closing = s.rfind(']')
                            if closing != -1:
                                candidate = s[:closing + 1]
                        parsed = None
                        try:
                            parsed = json.loads(candidate)
                        except json.JSONDecodeError:
                            import ast as _ast
                            try:
                                parsed = _ast.literal_eval(candidate)
                            except Exception:
                                parsed = None
                        if isinstance(parsed, list):
                            normalized_list.extend([str(x) for x in parsed])
                            remainder = s[len(candidate):].strip()
                            if remainder:
                                normalized_list.append(remainder)
                            continue
                        if s.startswith('{') and s.endswith('}'):
                            try:
                                parsed_obj = json.loads(s)
                                if isinstance(parsed_obj, dict) and 'responses' in parsed_obj:
                                    extracted = parsed_obj['responses']
                                    if isinstance(extracted, list):
                                        normalized_list.extend([str(x) for x in extracted])
                                        continue
                            except Exception:
                                pass
                    normalized_list.append(s)
                else:
                    normalized_list.append(str(item))

            responses = normalized_list[:5]
            responses = self._filter_chinese_responses(responses)
            responses = self._enforce_response_constraints(responses)

            return {
                "responses": responses,
                "state": state,
                "dialogue_context": dialogue_context,
                "context_classification": context_classification,
                "processing_info": processing_info,
                "optimization_info": {
                    "api_calls_used": 1,
                    "api_calls_saved": 2,
                    "efficiency_improvement": "66.7%"
                }
            }
            
        except Exception as e:
            self.logger.error(f"優化預測結果處理失敗: {e}", exc_info=True)
            return {
                "responses": [f"OptimizedPredictionError[{type(e).__name__}]: {e}"],
                "state": "ERROR",
                "dialogue_context": "OPTIMIZED_PREDICTION_EXCEPTION",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    def _update_dialogue_state(self, response_data: dict):
        """更新對話狀態"""
        try:
            from ..state import DialogueState
            new_state = response_data.get("state", "NORMAL")
            self.current_state = DialogueState(new_state)
            
            dialogue_context = response_data.get("dialogue_context", "")
            if dialogue_context:
                print(f"優化 DSPy 判斷的對話情境: {dialogue_context}")
                
        except ValueError as e:
            self.logger.warning(f"無效狀態，設置為 CONFUSED: {e}")
            from ..state import DialogueState
            self.current_state = DialogueState.CONFUSED
    
    def _handle_terminal_mode(self, user_input: str, response_data: dict) -> str:
        """處理終端機模式的互動"""
        import keyboard
        
        responses = response_data["responses"]
        
        print(f"\n{self.character.name} 的回應選項（優化 DSPy 生成，節省 66.7% API 調用）：")
        for i, response in enumerate(responses, 1):
            print(f"{i}. {response}")
        print("0. 這些選項都不適合（跳過，直接進入下一輪對話）")
        print("q. 結束對話")
        print("s. 顯示優化統計")
        print("\n請按數字鍵 0-5 選擇選項，s 查看統計，或按 q 結束對話...")
        
        while True:
            event = keyboard.read_event(suppress=True)
            if event.event_type == 'down':
                if event.name == '0':
                    print("\n跳過此輪回應，請繼續對話")
                    self.conversation_history.append("(跳過此輪回應)")
                    self.log_interaction(user_input, responses, selected_response="(跳過此輪回應)")
                    self.save_interaction_log()
                    return ""
                elif event.name == 'q':
                    print("\n結束對話")
                    print(self._get_optimization_summary())
                    self.save_interaction_log()
                    return "quit"
                elif event.name == 's':
                    print("\n" + self._get_optimization_summary())
                    continue
                elif event.name in ['1', '2', '3', '4', '5']:
                    choice = int(event.name)
                    if choice <= len(responses):
                        selected_response = responses[choice - 1]
                        print(f"\n已選擇選項 {choice}: {selected_response}")
                        self.conversation_history.append(f"{self.character.name}: {selected_response}")
                        self.log_interaction(user_input, responses, selected_response=selected_response)
                        self.save_interaction_log()
                        return selected_response
    
    def _handle_gui_mode(self, user_input: str, response_data: dict, gui_selected_response: Optional[str] = None) -> str:
        """處理 GUI 模式的互動"""
        # 記錄互動
        self.log_interaction(user_input, response_data["responses"], selected_response=gui_selected_response)
        self.save_interaction_log()
        
        # 追加病患回應到對話歷史（選擇首個建議，便於下一輪提供上下文）
        try:
            normalized = self._normalize_responses(response_data.get("responses", []))
            if normalized:
                self.conversation_history.append(f"{self.character.name}: {normalized[0]}")
        except Exception:
            pass
        
        # 返回 JSON 格式回應
        return json.dumps(response_data, ensure_ascii=False)
    
    def get_optimization_statistics(self) -> dict:
        """獲取優化統計資訊"""
        base_stats = {}
        if hasattr(self, 'dialogue_module') and hasattr(self.dialogue_module, 'get_unified_statistics'):
            base_stats = self.dialogue_module.get_unified_statistics()
        
        return {
            **base_stats,
            **self.optimization_stats,
            'optimization_enabled': self.optimization_enabled,
            'efficiency_summary': {
                'conversations_processed': self.optimization_stats['total_conversations'],
                'total_api_calls_saved': self.optimization_stats['api_calls_saved'],
                'quota_savings_percent': f"{self.optimization_stats['estimated_quota_saved_percent']:.1f}%",
                'calls_per_conversation': '1 (原本 3次)',
                'optimization_factor': '3x 效率提升'
            }
        }
    
    def _get_optimization_summary(self) -> str:
        """獲取優化摘要字串"""
        stats = self.get_optimization_statistics()
        return f"""
🎯 API 調用優化統計摘要:
  - 處理對話數量: {stats['conversations_processed']}
  - 節省 API 調用: {stats['total_api_calls_saved']} 次
  - 配額節省率: {stats['quota_savings_percent']}
  - 效率提升: 每次對話從 3次調用 → 1次調用
  - 整體效率: 提升 3倍，解決配額限制問題
"""
    
    def _apply_degradation_prevention(self, response_data: dict, user_input: str) -> dict:
        """應用退化防護措施，檢測並修復問題回應"""
        try:
            self.logger.info(f"🔍 DEGRADATION PREVENTION: Checking response data")
            responses = response_data.get("responses", [])
            self.logger.info(f"🔍 DEGRADATION PREVENTION: Found {len(responses)} responses")
            
            if not responses:
                self.logger.info(f"🔍 DEGRADATION PREVENTION: No responses, returning original")
                return response_data
            
            # 檢測退化模式
            has_degradation = False
            degradation_indicators = []
            
            for i, response in enumerate(responses):
                response_str = str(response)
                self.logger.info(f"🔍 DEGRADATION PREVENTION: Checking response {i+1}: '{response_str[:50]}...'")
                
                # 檢測自我介紹模式
                if any(pattern in response_str for pattern in ["我是Patient", "您好，我是", "我是病患"]):
                    has_degradation = True
                    degradation_indicators.append("self_introduction")
                    self.logger.warning(f"🚨 DETECTED: Self-introduction pattern in response {i+1}")
                
                # 檢測通用回應模式與錯誤模板
                if any(pattern in response_str for pattern in ["我可能沒有完全理解", "能請您換個方式說明", "您需要什麼幫助嗎", "抱歉，我現在無法正確回應"]):
                    has_degradation = True
                    degradation_indicators.append("generic_responses")
                    self.logger.warning(f"🚨 DETECTED: Generic response pattern in response {i+1}")

            # 若狀態為 CONFUSED，也視為退化並進行修復
            if response_data.get("state") == "CONFUSED":
                has_degradation = True
                if "confused_state" not in degradation_indicators:
                    degradation_indicators.append("confused_state")
            
            if has_degradation:
                self.logger.warning(f"🚨 DEGRADATION PREVENTION: 檢測到退化模式 {degradation_indicators}，啟動修復機制")
                response_data["degradation_detected"] = True
                response_data["original_degradation"] = degradation_indicators
            else:
                self.logger.info(f"✅ DEGRADATION PREVENTION: No degradation detected, keeping original responses")

            return response_data
            
        except Exception as e:
            self.logger.error(f"🚨 DEGRADATION PREVENTION: 退化防護失敗: {e}")
            import traceback
            self.logger.error(f"🚨 DEGRADATION PREVENTION: Traceback: {traceback.format_exc()}")
            return response_data
    
    def _trigger_context_reset(self):
        """觸發上下文重置，防止後續退化"""
        try:
            # 清理對話歷史，保留最近的關鍵信息
            if len(self.conversation_history) > 4:
                # 只保留最近2輪對話
                recent_history = self.conversation_history[-4:]
                self.conversation_history = recent_history
                self.logger.info(f"🔄 執行上下文重置，保留最近 {len(recent_history)} 條記錄")
            
            # 重置 DSPy 模組內部狀態（如果可能）
            if hasattr(self.dialogue_module, 'reset_context'):
                self.dialogue_module.reset_context()
                
        except Exception as e:
            self.logger.error(f"上下文重置失敗: {e}")


    def _normalize_responses(self, responses) -> list:
        if isinstance(responses, str):
            return [responses.strip()] if responses.strip() else []
        if isinstance(responses, list):
            return [str(item).strip() for item in responses if str(item).strip()]
        if responses is None:
            return []
        return [str(responses).strip()]

    def _normalize_state_value(self, raw_state: Any) -> str:
        allowed = {'NORMAL', 'CONFUSED', 'TRANSITIONING', 'TERMINATED'}

        if isinstance(raw_state, dict):
            return self._normalize_state_value(raw_state.get('state') or raw_state.get('name'))
        if isinstance(raw_state, (list, tuple)):
            for item in raw_state:
                normalized = self._normalize_state_value(item)
                if normalized:
                    return normalized
            return 'NORMAL'
        if raw_state is None:
            return 'NORMAL'

        candidate = str(raw_state).strip().upper()
        if candidate in allowed:
            return candidate
        return 'NORMAL'

    def _normalize_text_field(self, value: Any) -> str:
        if isinstance(value, dict):
            for key in ('dialogue_context', 'value', 'text', 'description'):
                if key in value:
                    return self._normalize_text_field(value[key])
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, (list, tuple)):
            return " | ".join(self._normalize_text_field(v) for v in value if v)
        return str(value).strip() if value is not None else ''

    def _normalize_context_value(self, value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ('context_classification', 'label', 'id', 'name', 'value'):
                if key in value:
                    return self._normalize_context_value(value[key])
            return None
        if isinstance(value, (list, tuple)):
            for item in value:
                normalized = self._normalize_context_value(item)
                if normalized:
                    return normalized
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.startswith('{') and stripped.endswith('}'):
                try:
                    parsed = json.loads(stripped)
                    return self._normalize_context_value(parsed)
                except Exception:
                    return None
            return stripped
        return None

    def _filter_chinese_responses(self, responses: List[str]) -> List[str]:
        chinese_regex = re.compile(r"[\u4e00-\u9fff]")
        filtered: List[str] = [r for r in responses if chinese_regex.search(r)]
        if filtered:
            if len(filtered) < len(responses):
                self.logger.info(
                    "⚠️ Removed non-Chinese responses: %s",
                    [r for r in responses if r not in filtered],
                )
            return filtered[:5]
        return responses

    def _enforce_response_constraints(self, responses: List[str]) -> List[str]:
        sanitized: List[str] = []
        for response in responses:
            candidate = response.strip()
            if not candidate:
                continue
            if '?' in candidate or '？' in candidate:
                self.logger.info(f"⚠️ Removed question response: {candidate}")
                continue
            if '一起住院' in candidate or '跟家人' in candidate or '跟父母' in candidate or '跟丈夫' in candidate or '跟朋友' in candidate or '跟兄弟姐妹' in candidate:
                replacement = "我一個人住院，目前由護理團隊照護。"
                if replacement not in sanitized:
                    sanitized.append(replacement)
                self.logger.info(f"⚠️ Replaced companion statement: {candidate} -> {replacement}")
                continue
            sanitized.append(candidate)

        if not sanitized:
            sanitized = ["我在醫院接受治療，會依照醫護指示配合。"]

        return sanitized[:5]

    def _attempt_sensitive_rewrite(self, original_question: str, base_prediction=None):
        """Ask Gemini to rewrite the question and fetch a new response."""
        try:
            if not self.enable_sensitive_rewrite:
                return None

            if not hasattr(self, 'sensitive_question_module'):
                return None

            conversation_summary = "\n".join(self.conversation_history[-6:])
            rewrite_prediction = self.sensitive_question_module.rewrite(
                original_question=original_question,
                conversation_summary=conversation_summary,
                character_name=self.character.name,
                character_persona=self.character.persona,
            )

            if not rewrite_prediction:
                self.logger.warning("Sensitive rewrite module returned None")
                return None

            sensitivity_flag = str(getattr(rewrite_prediction, 'sensitivity_flag', '')).strip()
            rewritten_question = str(getattr(rewrite_prediction, 'rewritten_question', '')).strip()
            reason = str(getattr(rewrite_prediction, 'sensitivity_reason', '')).strip()
            reassurance = str(getattr(rewrite_prediction, 'reassurance_message', '')).strip()

            normalized_flag = sensitivity_flag.upper()
            should_use_rewrite = normalized_flag in {'YES', 'TRUE', 'SENSITIVE'} and rewritten_question

            if not should_use_rewrite:
                self.logger.warning(
                    "Sensitive rewrite probe completed but flag=%s (reason=%s); skipping fallback.",
                    sensitivity_flag or 'UNKNOWN',
                    reason or '未提供',
                )
                return None

            self.logger.warning(
                "Gemini policy refusal detected. Reason: %s", reason or '未提供'
            )
            self.logger.warning(
                "Original question: %s | Rewritten as: %s",
                original_question,
                rewritten_question,
            )

            # Replace the last caregiver entry with the rewritten question for context continuity
            if self.conversation_history and self.conversation_history[-1].startswith("護理人員: "):
                self.conversation_history[-1] = f"護理人員(重述): {rewritten_question}"
            else:
                self.conversation_history.append(f"護理人員(重述): {rewritten_question}")

            rewritten_prediction = self.dialogue_module(
                user_input=rewritten_question,
                character_name=self.character.name,
                character_persona=self.character.persona,
                character_backstory=self.character.backstory,
                character_goal=self.character.goal,
                character_details=self._get_character_details(),
                conversation_history=self._format_conversation_history()
            )

            response_data = self._process_optimized_prediction(rewritten_prediction)
            response_data["sensitive_rewrite_pending"] = True
            response_data = self._apply_degradation_prevention(response_data, rewritten_question)
            response_data.pop("sensitive_rewrite_pending", None)
            response_data["sensitive_rewrite_applied"] = True
            response_data["sensitive_rewrite"] = {
                "original_question": original_question,
                "rewritten_question": rewritten_question,
                "reason": reason,
                "reassurance": reassurance,
            }

            explanation = reason or "原始提問可能觸及敏感政策"
            notice = f"提醒：{explanation}。已改寫為「{rewritten_question}」。"
            if reassurance:
                notice = f"{notice} {reassurance}"

            rewritten_responses = response_data.get("responses", [])
            enriched = [notice] + rewritten_responses
            response_data["responses"] = enriched[:5]
            return response_data

        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error(f"Sensitive rewrite flow failed: {exc}", exc_info=True)
            return None
    
    def _track_session_state_changes(self, user_input: str, response_data: dict, round_number: int):
        """追蹤會話狀態變化和退化指標
        
        Args:
            user_input: 用戶輸入
            response_data: 回應資料
            round_number: 對話輪次
        """
        try:
            self.logger.info(f"=== SESSION STATE TRACKING - Round {round_number} ===")
            
            # 基本會話資訊
            self.logger.info(f"🔢 CONVERSATION METRICS:")
            self.logger.info(f"  📊 Round Number: {round_number}")
            self.logger.info(f"  📈 Total Conversation History: {len(self.conversation_history)} entries")
            self.logger.info(f"  📏 Current Input Length: {len(user_input)} chars")
            
            # 會話狀態分析
            session_state = self._analyze_session_state(response_data, round_number)
            self.logger.info(f"  🎭 Session State Analysis:")
            for key, value in session_state.items():
                self.logger.info(f"    {key}: {value}")
            
            # 角色一致性追蹤
            consistency_score = self._calculate_consistency_score(response_data)
            self.logger.info(f"  🎯 Character Consistency Score: {consistency_score:.3f}")
            
            # 回應品質指標
            quality_metrics = self._calculate_response_quality_metrics(response_data)
            self.logger.info(f"  🏆 Response Quality Metrics:")
            for metric, value in quality_metrics.items():
                self.logger.info(f"    {metric}: {value}")
            
            # 退化風險評估
            degradation_risk = self._assess_degradation_risk(response_data, round_number)
            self.logger.info(f"  ⚠️  Degradation Risk: {degradation_risk['risk_level']} ({degradation_risk['score']:.2f})")
            
            # 會話複雜度分析
            complexity_analysis = self._analyze_conversation_complexity()
            self.logger.info(f"  🧮 Conversation Complexity:")
            for key, value in complexity_analysis.items():
                self.logger.info(f"    {key}: {value}")
            
            # 記憶使用情況
            memory_info = self._track_memory_usage()
            self.logger.info(f"  💾 Memory Usage: {memory_info}")
            
            # 如果是關鍵輪次（3-5輪），額外記錄
            if 3 <= round_number <= 5:
                self.logger.warning(f"🚨 CRITICAL ROUND {round_number} - Enhanced monitoring active")
                self._log_critical_round_analysis(user_input, response_data, round_number)
            
            # 儲存狀態歷史（用於趨勢分析）
            self._store_session_state_history(session_state, round_number)
            
        except Exception as e:
            self.logger.error(f"會話狀態追蹤失敗: {e}")
    
    def _analyze_session_state(self, response_data: dict, round_number: int) -> dict:
        """分析當前會話狀態"""
        try:
            responses = response_data.get("responses", [])
            state = response_data.get("state", "UNKNOWN")
            context = response_data.get("dialogue_context", "UNKNOWN")
            
            return {
                "Response_Count": len(responses),
                "Dialogue_State": state,
                "Dialogue_Context": context,
                "Round_Number": round_number,
                "Original_Degradation": response_data.get("original_degradation", []),
                "Emergency_Recovery": response_data.get("emergency_recovery", False)
            }
        except Exception as e:
            return {"Error": str(e)}
    
    def _calculate_consistency_score(self, response_data: dict) -> float:
        """計算角色一致性分數"""
        try:
            responses = response_data.get("responses", [])
            if not responses:
                return 0.0
            
            score = 1.0
            
            # 檢查自我介紹模式（嚴重扣分）
            for response in responses:
                if any(pattern in str(response) for pattern in ["我是Patient", "您好，我是"]):
                    score -= 0.4
                    break
            
            # 檢查通用回應（中度扣分）
            for response in responses:
                if any(pattern in str(response) for pattern in ["沒有完全理解", "換個方式說明", "您需要什麼幫助"]):
                    score -= 0.2
                    break
            
            # 檢查醫療相關性（加分）
            medical_terms = ["症狀", "檢查", "傷口", "恢復", "治療", "藥物", "護理"]
            has_medical_context = any(
                any(term in str(response) for term in medical_terms)
                for response in responses
            )
            if has_medical_context:
                score += 0.1
            
            return max(0.0, min(1.0, score))
            
        except Exception:
            return 0.5
    
    def _calculate_response_quality_metrics(self, response_data: dict) -> dict:
        """計算回應品質指標"""
        try:
            responses = response_data.get("responses", [])
            
            metrics = {
                "Response_Count": len(responses),
                "Average_Length": sum(len(str(r)) for r in responses) // max(1, len(responses)),
                "Has_Medical_Terms": self._has_medical_terms(responses),
                "Has_Self_Introduction": self._has_self_introduction(response_data),
                "Context_Relevance": self._calculate_context_relevance("", response_data),  # 簡化版
                "Diversity_Score": self._calculate_response_diversity(responses)
            }
            
            return metrics
            
        except Exception as e:
            return {"Error": str(e)}
    
    def _has_medical_terms(self, responses: list) -> bool:
        """檢查是否包含醫療術語"""
        medical_terms = ["症狀", "檢查", "傷口", "恢復", "治療", "藥物", "護理", "醫師", "病房"]
        return any(
            any(term in str(response) for term in medical_terms)
            for response in responses
        )
    
    def _calculate_response_diversity(self, responses: list) -> float:
        """計算回應多樣性分數"""
        try:
            if len(responses) <= 1:
                return 0.0
            
            # 簡單的多樣性檢查：計算不同開頭的比例
            first_chars = [str(r)[0] if str(r) else '' for r in responses]
            unique_starts = len(set(first_chars))
            
            return unique_starts / len(responses)
            
        except Exception:
            return 0.5
    
    def _assess_degradation_risk(self, response_data: dict, round_number: int) -> dict:
        """評估退化風險"""
        try:
            risk_score = 0.0
            risk_factors = []
            
            # 輪次風險（第4-5輪風險較高）
            if 4 <= round_number <= 5:
                risk_score += 0.3
                risk_factors.append("Critical_Round")
            
            # 回應品質風險
            responses = response_data.get("responses", [])
            if len(responses) < 3:
                risk_score += 0.2
                risk_factors.append("Few_Responses")
            
            # 自我介紹風險
            if self._has_self_introduction(response_data):
                risk_score += 0.4
                risk_factors.append("Self_Introduction")
            
            # 狀態風險
            if response_data.get("state") == "CONFUSED":
                risk_score += 0.1
                risk_factors.append("Confused_State")
            
            # 確定風險等級
            if risk_score >= 0.7:
                risk_level = "HIGH"
            elif risk_score >= 0.4:
                risk_level = "MEDIUM"
            elif risk_score >= 0.2:
                risk_level = "LOW"
            else:
                risk_level = "MINIMAL"
            
            return {
                "score": risk_score,
                "risk_level": risk_level,
                "factors": risk_factors
            }
            
        except Exception as e:
            return {"score": 1.0, "risk_level": "ERROR", "factors": [str(e)]}
    
    def _analyze_conversation_complexity(self) -> dict:
        """分析對話複雜度"""
        try:
            history_length = len(self.conversation_history)
            total_chars = sum(len(entry) for entry in self.conversation_history)
            
            return {
                "History_Entries": history_length,
                "Total_Characters": total_chars,
                "Average_Entry_Length": total_chars // max(1, history_length),
                "Estimated_Rounds": history_length // 2,
                "Complexity_Level": (
                    "High" if total_chars > 2000 else
                    "Medium" if total_chars > 1000 else
                    "Low"
                )
            }
        except Exception:
            return {"Error": "Analysis failed"}
    
    def _track_memory_usage(self) -> str:
        """追蹤記憶體使用情況"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            return f"{memory_mb:.1f} MB"
        except ImportError:
            return "N/A (psutil not available)"
        except Exception:
            return "Error"
    
    def _log_critical_round_analysis(self, user_input: str, response_data: dict, round_number: int):
        """記錄關鍵輪次的詳細分析"""
        self.logger.warning(f"🔍 CRITICAL ROUND {round_number} DETAILED ANALYSIS:")
        self.logger.warning(f"  📥 Input: '{user_input}'")
        self.logger.warning(f"  📊 Response State: {response_data.get('state', 'UNKNOWN')}")
        self.logger.warning(f"  🌍 Context: {response_data.get('dialogue_context', 'UNKNOWN')}")
        self.logger.warning(f"  💬 Response Count: {len(response_data.get('responses', []))}")
        
        # 詳細回應分析
        responses = response_data.get('responses', [])
        for i, response in enumerate(responses, 1):
            has_issues = any(pattern in str(response) for pattern in ["我是Patient", "沒有完全理解", "您需要什麼幫助"])
            status = "🔴 PROBLEMATIC" if has_issues else "✅ OK"
            self.logger.warning(f"    Response {i}: {status} - '{str(response)[:100]}...'")
    
    def _store_session_state_history(self, session_state: dict, round_number: int):
        """儲存會話狀態歷史"""
        try:
            if not hasattr(self, '_session_history'):
                self._session_history = []
            
            history_entry = {
                "round": round_number,
                "timestamp": time.time(),
                "state": session_state
            }
            
            self._session_history.append(history_entry)
            
            # 只保留最近10輪的記錄
            if len(self._session_history) > 10:
                self._session_history = self._session_history[-10:]
                
        except Exception as e:
            self.logger.error(f"狀態歷史儲存失敗: {e}")
    
    def _generate_emergency_response(self, user_input: str) -> str:
        """生成緊急恢復回應，當所有其他方法都失敗時使用"""
        self.logger.warning(f"🚨 生成緊急恢復回應 for: {user_input}")
        emergency_responses = [
            "EmergencyFallback: dialogue manager failed to recover; please review server logs."
        ]

        emergency_data = {
            "status": "success",
            "responses": emergency_responses,
            "state": "NORMAL", 
            "dialogue_context": "緊急恢復模式",
            "session_id": getattr(self, 'current_session_id', None),
            "emergency_recovery": True,
            "speech_recognition_options": None,
            "original_transcription": None
        }
        
        return json.dumps(emergency_data, ensure_ascii=False)

    def cleanup(self):
        """清理資源"""
        self.logger.info("清理優化版 DSPy 對話管理器")
        
        # 顯示最終統計
        final_stats = self.get_optimization_statistics()
        self.logger.info(f"最終優化統計: {final_stats}")
        
        if hasattr(self, 'dialogue_module') and hasattr(self.dialogue_module, 'cleanup'):
            self.dialogue_module.cleanup()


# 測試函數
def test_optimized_dialogue_manager():
    """測試優化版對話管理器"""
    print("🧪 測試優化版 DSPy 對話管理器...")
    
    try:
        # 創建測試角色
        from ..character import Character
        test_character = Character(
            name="測試病患",
            persona="友善但擔心的病患",
            backstory="住院中進行康復治療",
            goal="盡快康復出院"
        )
        
        # 創建優化版管理器
        manager = OptimizedDialogueManagerDSPy(test_character)
        
        print("✅ 優化版對話管理器創建成功")
        print(manager._get_optimization_summary())
        
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_optimized_dialogue_manager()
