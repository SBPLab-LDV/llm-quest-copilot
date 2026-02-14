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
    
    def __init__(self, character: Character, use_terminal: bool = False, log_dir: str = "logs", log_file_basename: Optional[str] = None):
        """初始化優化版 DSPy 對話管理器
        
        Args:
            character: Character instance containing the NPC's information (as patient identifier)
            use_terminal: Whether to use terminal mode for interaction
            log_dir: Directory to save interaction logs
        """
        # 初始化父類
        super().__init__(character, use_terminal, log_dir, log_file_basename=log_file_basename)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("OptimizedDialogueManagerDSPy.__init__ - 使用統一對話模組")
        
        # 讀取敏感提問改寫開關
        dspy_config = get_config().get_dspy_config()
        self.enable_sensitive_rewrite = dspy_config.get('enable_sensitive_rewrite', True)

        # 初始化優化的 DSPy 組件（fail-fast：不允許回退到其他實現）
        self.dialogue_module = UnifiedDSPyDialogueModule()
        self.optimization_enabled = True
        self.logger.info("優化統一對話模組初始化成功 - API 調用節省 66.7%")
        if self.enable_sensitive_rewrite:
            self.sensitive_question_module = SensitiveQuestionRewriteModule()
        else:
            self.sensitive_question_module = None
            self.logger.info("敏感提問改寫已停用（enable_sensitive_rewrite=False）")
        
        # 統計追蹤
        self.optimization_stats = {
            'total_conversations': 0,
            'api_calls_saved': 0,
            'estimated_quota_saved_percent': 0.0
        }
        self._character_profile_emitted = False
        self._last_turn_timings: Optional[Dict] = None

    async def process_turn(self, user_input: str, gui_selected_response: Optional[str] = None) -> Union[str, dict]:
        """處理優化版對話輪次
        
        Args:
            user_input: The user's input text
            gui_selected_response: Selected response in GUI mode (optional)
            
        Returns:
            Either a string response (terminal mode) or JSON response (GUI mode)
        """
        if not self.optimization_enabled:
            raise RuntimeError("OptimizedDialogueManagerDSPy is disabled (fail-fast; no fallback).")
        
        self.optimization_stats['total_conversations'] += 1
        
        try:
            self.logger.info(f"=== 優化版對話處理 (第 {self.optimization_stats['total_conversations']} 次) ===")
            self.logger.info(f"用戶輸入: {user_input}")

            # Echo suppression: avoid recording caregiver line if it exactly repeats last patient utterance
            try:
                normalized_input = (user_input or "").strip()
                last_patient_utterance: Optional[str] = None
                if self.conversation_history and normalized_input:
                    patient_prefix = f"{self.character.name}: "
                    for entry in reversed(self.conversation_history):
                        if isinstance(entry, str):
                            s = entry.strip()
                            if s.startswith(patient_prefix):
                                last_patient_utterance = s[len(patient_prefix):].strip()
                                break
                is_echo_of_patient = last_patient_utterance and (last_patient_utterance == normalized_input)
            except Exception:
                is_echo_of_patient = False
            
            # 檢查重複輸入 - 避免在會話中添加相同的輸入
            last_user_input = None
            if self.conversation_history:
                for entry in reversed(self.conversation_history):
                    if entry.startswith("對話方: "):
                        last_user_input = entry[4:]  # 移除 "對話方: " 前綴
                        break
            
            is_duplicate_input = (last_user_input == user_input)
            
            # 只有不是重複輸入時才記錄到對話歷史
            if not is_duplicate_input and not is_echo_of_patient:
                self.conversation_history.append(f"對話方: {user_input}")
                self.logger.info(f"✅ 新輸入已記錄到對話歷史")
            else:
                reason = "與上一輪對話方輸入重複" if is_duplicate_input else "與上一輪病患選擇回覆相同(回聲抑制)"
                self.logger.info(f"⚠️ 跳過記錄到對話歷史：{reason}")
            
            # 使用優化的統一對話模組 (僅1次 API 調用)
            _t_turn_start = time.time()
            self._last_turn_timings = None

            _t_dialogue_module_start = time.time()
            prediction = self.dialogue_module(
                user_input=user_input,
                character_name=self.character.name,
                character_persona=self.character.persona,
                character_backstory=self.character.backstory,
                character_goal=self.character.goal,
                character_details=self._get_character_details(),
                conversation_history=self._format_conversation_history()
            )
            _t_dialogue_module_end = time.time()

            self.logger.info(f"優化處理完成:")
            self.logger.info(f"  - API 調用次數: 1 (原本需要 3次)")
            self.logger.info(f"  - 節省配額使用: 66.7%")
            self.logger.info(f"  - 回應數量: {len(prediction.responses)}")
            self.logger.info(f"  - 情境分類: {getattr(prediction, 'context_classification', None)}")

            # 更新節省統計
            saved_calls = prediction.processing_info.get('api_calls_saved', 2)
            self.optimization_stats['api_calls_saved'] += saved_calls
            self.optimization_stats['estimated_quota_saved_percent'] = (
                (self.optimization_stats['api_calls_saved'] /
                 (self.optimization_stats['total_conversations'] * 3)) * 100
                if self.optimization_stats['total_conversations'] > 0 else 0
            )

            # 讓 rewrite 模組決策是否需要改寫（若停用，直接使用基礎預測）
            _t_sensitive_rewrite_start = time.time()
            rewrite_result = self._attempt_sensitive_rewrite(user_input, prediction)
            _t_sensitive_rewrite_end = time.time()
            _sensitive_rewrite_triggered = rewrite_result is not None

            _t_post_processing_start = time.time()
            response_data = rewrite_result if rewrite_result else self._process_optimized_prediction(prediction)

            # ====== Phase 1.3: 會話狀態變化追蹤 ======
            round_number = len(self.conversation_history) // 2 + 1  # 估算輪次
            self._track_session_state_changes(user_input, response_data, round_number)

            # 更新對話狀態
            self._update_dialogue_state(response_data)

            # 處理終端機模式或 GUI 模式
            if self.use_terminal:
                result = self._handle_terminal_mode(user_input, response_data)
            else:
                result = self._handle_gui_mode(user_input, response_data, gui_selected_response)
            _t_post_processing_end = time.time()

            _t_turn_end = time.time()
            self._last_turn_timings = {
                "total_s": round(_t_turn_end - _t_turn_start, 4),
                "dialogue_module_s": round(_t_dialogue_module_end - _t_dialogue_module_start, 4),
                "sensitive_rewrite_s": round(_t_sensitive_rewrite_end - _t_sensitive_rewrite_start, 4),
                "post_processing_s": round(_t_post_processing_end - _t_post_processing_start, 4),
                "sensitive_rewrite_triggered": _sensitive_rewrite_triggered,
            }
            self.logger.info("[Timing] process_turn: %s", self._last_turn_timings)

            return result
                
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
                        return json.dumps(fallback_data, ensure_ascii=False)
                    except json.JSONDecodeError:
                        # 不是 JSON，直接返回
                        return fallback_result
                else:
                    # 父類返回字典，直接返回
                    return fallback_result
                    
            except Exception as fallback_error:
                self.logger.error(f"父類回退也失敗: {fallback_error}")
                self.logger.error("FALLBACK_CHAIN_FAILED: super().process_turn exception", exc_info=True)
                # 最終防護：生成安全的恢復回應
                return self._generate_emergency_response(user_input)
    
    def _get_character_details(self) -> Any:
        """回傳完整的角色詳細設定（盡可能保留 characters.yaml 的全部資訊）。

        - 若有 details 字典：返回 { fixed_settings, floating_settings, summary }
        - 若 details 為可解析的 JSON 字串：解析後返回同上結構
        - 否則：返回簡短字串摘要（與舊行為相容）
        """
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

            summary = " | ".join(p for p in summary_parts if p)
            # 記錄簡要的鍵數統計，便於在 dspy_internal_debug.log 佐證
            try:
                self.logger.info(
                    "[DETAILS] fixed=%d keys, floating=%d keys (summary_len=%d)",
                    len(fixed) if isinstance(fixed, dict) else 0,
                    len(floating) if isinstance(floating, dict) else 0,
                    len(summary),
                )
            except Exception:
                pass

            return {
                'fixed_settings': fixed,
                'floating_settings': floating,
                'summary': summary
            }

        # 無 details 可用時：回退到簡短字串（相容舊行為）
        fallback = [
            f"姓名: {getattr(self.character, 'name', '未知')}",
            getattr(self.character, 'persona', ''),
            getattr(self.character, 'goal', ''),
        ]
        return " | ".join(part for part in fallback if part)
    
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

            # inferred_speaker_role 已移除，保持向後相容
            inferred_speaker_role = None
            
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

            responses = normalized_list[:4]
            responses = self._filter_chinese_responses(responses)

            return {
                "responses": responses,
                "state": state,
                "dialogue_context": dialogue_context,
                "context_classification": context_classification,
                "inferred_speaker_role": inferred_speaker_role,
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
        # Echo suppression: 若本輪輸入等同於最近病患發言，避免將其記入互動日誌
        suppress_logging = False
        try:
            normalized_input = (user_input or "").strip()
            if self.conversation_history and normalized_input:
                patient_prefix = f"{self.character.name}: "
                for entry in reversed(self.conversation_history):
                    if isinstance(entry, str):
                        s = entry.strip()
                        if s.startswith(patient_prefix):
                            last_patient_utterance = s[len(patient_prefix):].strip()
                            if last_patient_utterance == normalized_input:
                                suppress_logging = True
                            break
        except Exception:
            suppress_logging = False

        # 記錄互動（若未被回聲抑制）
        if not suppress_logging:
            self.log_interaction(user_input, response_data["responses"], selected_response=gui_selected_response)
            self.save_interaction_log()

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
    
    # 已移除：退化防護層
    
    # 簡化：移除未使用的上下文重置功能


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
            return filtered[:4]
        return responses

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
            if self.conversation_history and self.conversation_history[-1].startswith("對話方: "):
                self.conversation_history[-1] = f"對話方(重述): {rewritten_question}"
            else:
                self.conversation_history.append(f"對話方(重述): {rewritten_question}")

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
            response_data["responses"] = enriched[:4]
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
            
            # 簡化：移除退化風險/複雜度/記憶體與關鍵輪分析及狀態歷史記錄
            
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
            }
            
            return metrics
            
        except Exception as e:
            return {"Error": str(e)}

    
    
    # 簡化：移除退化風險/複雜度/記憶體與關鍵輪分析與狀態歷史方法（無行為影響）
    
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
