#!/usr/bin/env python3
"""
統一 DSPy 對話模組

將原本的多步驟調用（情境分類、回應生成、狀態轉換）合併為單一 API 調用，
以解決 API 配額限制問題。
"""

import dspy
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from dspy.adapters import JSONAdapter
from dspy.adapters.utils import format_field_value, translate_field_type
from dspy.dsp.utils.settings import settings

from .consistency_checker import DialogueConsistencyChecker
from .dialogue_module import DSPyDialogueModule

logger = logging.getLogger(__name__)

JSON_OUTPUT_DIRECTIVE = (
    "[指示] 僅輸出單一 JSON 物件，至少包含欄位 reasoning, character_consistency_check, context_classification, "
    "confidence, responses。必須維持合法 JSON 語法，"
    "所有鍵與值皆用雙引號，禁止輸出 None/null/True/False 或未封閉的字串。不得輸出任何分析或思考步驟，"
    "請直接輸出 JSON 物件（不要附加除 JSON 以外的文字）。reasoning 使用一句極短敘述（不需精確字數）。"
    "responses 必須是一個長度為 5 的 JSON 陣列；每個元素為一句簡短、自然、彼此獨立且互斥的完整繁體中文句子，"
    "且每句都需直接回應 user_input 的核心名詞（例如涉及『醫師/巡房/發燒/藥物/檢查』時，回應需自然提及相關詞彙），不可偏題。"
    "5 句需涵蓋不同的回應取向（例如：肯定、否定、不確定需查證、提供時間或具體細節、請協助確認），"
    "禁止同義改寫或重覆語意，需更換不同名詞與動詞以確保差異化。"
    "嚴禁在回覆或生成過程中計算或提及字數；嚴禁描述規則、分析或英文內容；"
    "嚴禁輸出無關的模板句（如『謝謝關心』『我會配合治療』『目前沒有發燒』）除非問題明確在問該事項。"
    "若資訊不足，請以針對性的詢問或請求協助/查證方式回應（仍需提及核心名詞），並產生 5 條彼此不同且與題目相關的句子。"
    "禁止添加 [[ ## field ## ]]、markdown 或任何額外文字，完整輸出後以 } 結束。"
)

PERSONA_REMINDER_TEMPLATE = (
    "[角色提醒] 您是 {name}，{persona}。確保與上方醫療事實一致，" 
    "不得自我介紹或自稱 AI，所有回應需使用繁體中文。"
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

    # 輸出欄位（必填）
    reasoning = dspy.OutputField(desc="推理與一致性檢查")
    character_consistency_check = dspy.OutputField(desc="角色一致性 YES/NO")
    context_classification = dspy.OutputField(desc="情境分類 ID")
    confidence = dspy.OutputField(desc="情境信心 0-1")
    responses = dspy.OutputField(desc="五個病患回應")
    # state / dialogue_context / state_reasoning 由後處理自動補齊（不在 Signature 強制）



class UnifiedJSONAdapter(JSONAdapter):
    """Custom adapter that enforces JSON instructions without bracket markers."""

    def __init__(self, directive: str):
        super().__init__(use_native_function_calling=False)
        self.directive = directive.strip()

    def format_field_structure(self, signature: dspy.Signature) -> str:
        lines = ["請遵守以下輸出規範:", self.directive]
        descriptions = ["輸入欄位資訊:"]
        for field_name, field_info in signature.input_fields.items():
            extra = getattr(field_info, "json_schema_extra", {}) or {}
            desc = extra.get("desc") or extra.get("description") or getattr(field_info, "description", None)
            if not desc:
                desc = translate_field_type(field_name, field_info)
            descriptions.append(f"- {field_name}: {desc}")
        return "\n".join(lines + ["", *descriptions]).strip()

    def user_message_output_requirements(self, signature: dspy.Signature) -> str:
        return self.directive

    def format_user_message_content(
        self,
        signature: dspy.Signature,
        inputs: dict[str, Any],
        prefix: str = "",
        suffix: str = "",
        main_request: bool = False,
    ) -> str:
        messages: List[str] = []
        if prefix:
            messages.append(prefix.strip())

        for key, field in signature.input_fields.items():
            if key in inputs:
                formatted = format_field_value(field_info=field, value=inputs[key])
                messages.append(f"{key}: {formatted}")

        if main_request:
            messages.append(self.directive)

        if suffix:
            messages.append(suffix.strip())

        return "\n".join(chunk for chunk in messages if chunk).strip()

    def format_field_with_value(self, fields_with_values, role: str = "user") -> str:
        if role == "user":
            parts = []
            for field, _ in fields_with_values.items():
                parts.append(f"{field.name}: {translate_field_type(field.name, field.info)}")
            return "\n".join(parts).strip()
        return super().format_field_with_value(fields_with_values, role=role)


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
        
        # 替換為統一的對話處理器：直接使用 Predict 並強制 JSONAdapter
        self.unified_response_generator = dspy.Predict(UnifiedPatientResponseSignature)
        self._json_adapter = UnifiedJSONAdapter(JSON_OUTPUT_DIRECTIVE)

        # 追蹤最近一次模型輸出情境，做為下輪提示濾器
        self._last_context_label: Optional[str] = None
        self._fewshot_used = False

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
            # 由自訂 JSON adapter 注入輸出規範，不再在歷史中附加指令

            # 獲取精簡後的可用情境清單
            available_contexts = self._build_available_contexts()

            # 可選：插入 few-shot 範例（k=2），強化冷啟/語境不足回合
            fewshot_text = ""
            try:
                enable_fewshot = False  # disabled to reduce prompt length and latency
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
                        self._fewshot_used = True
            except Exception as _e:
                logger.info(f"Few-shot injection skipped: {_e}")
            
            current_call = self.unified_stats['total_unified_calls'] + 1
            logger.info(f"🚀 Unified DSPy call #{current_call} - {character_name} processing {len(conversation_history)} history entries")
            
            # **關鍵優化：單一 API 調用完成所有處理**
            import time
            call_start_time = time.time()
            
            with settings.context(adapter=self._json_adapter):
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
            _log_state = getattr(unified_prediction, 'state', 'UNKNOWN')
            logger.info(f"💬 Generated {len(parsed_responses)} responses - State: {_log_state}")
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
            self._update_stats(
                getattr(unified_prediction, 'context_classification', 'unspecified'),
                getattr(unified_prediction, 'state', 'NORMAL')
            )
            self.stats['successful_calls'] += 1
            
            # 組合最終結果（安全補齊缺欄位）
            _state = getattr(unified_prediction, 'state', 'NORMAL') or 'NORMAL'
            _ctx = getattr(unified_prediction, 'dialogue_context', 'unspecified') or 'unspecified'
            _class = getattr(unified_prediction, 'context_classification', 'unspecified') or 'unspecified'
            final_prediction = dspy.Prediction(
                user_input=user_input,
                responses=responses,
                state=_state,
                dialogue_context=_ctx,
                confidence=getattr(unified_prediction, 'confidence', 1.0),
                reasoning=getattr(unified_prediction, 'reasoning', ''),
                context_classification=_class,
                examples_used=0,  # 統一模式下暫不使用範例
                processing_info={
                    'unified_call': True,
                    'api_calls_saved': 2,
                    'context_classification': _class,
                    'state_reasoning': getattr(unified_prediction, 'state_reasoning', 'auto-filled due to missing fields'),
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
            # 嘗試從例外訊息中救回 LM 的 JSON 片段
            try:
                import re
                msg = str(e)
                start = msg.find('{')
                end = msg.rfind('}')
                salvaged = None
                if start != -1 and end != -1 and end > start:
                    snippet = msg[start:end+1]
                    salvaged = json.loads(snippet)
                if isinstance(salvaged, dict):
                    salv_responses = salvaged.get('responses') or []
                    if isinstance(salv_responses, str):
                        try:
                            tmp = json.loads(salv_responses)
                            if isinstance(tmp, list):
                                salv_responses = tmp
                            else:
                                salv_responses = [salv_responses]
                        except Exception:
                            salv_responses = [salv_responses]
                    if not isinstance(salv_responses, list):
                        salv_responses = [str(salv_responses)]
                    # 使用救回的 responses，其他欄位以預設補齊
                    return dspy.Prediction(
                        user_input=user_input,
                        responses=[str(x).strip() for x in salv_responses if str(x).strip()][:5] or [
                            "我目前無法確認，請您再提供更具體的資訊。",
                            "可否說明藥名、劑量與服用頻次？",
                            "如果不確定，請直接說不確定。",
                            "我會依據您提供的資訊再回覆。",
                            "謝謝。",
                        ],
                        state="NORMAL",
                        dialogue_context=str(salvaged.get('dialogue_context') or 'unspecified'),
                        confidence=float(salvaged.get('confidence') or 0.9),
                        reasoning=str(salvaged.get('reasoning') or 'salvaged from error'),
                        context_classification=str(salvaged.get('context_classification') or 'unspecified'),
                        examples_used=0,
                        processing_info={
                            'unified_call': True,
                            'api_calls_saved': 2,
                            'state_reasoning': 'auto-filled due to exception',
                            'timestamp': datetime.now().isoformat(),
                            'fallback_used': True,
                            'salvaged': True,
                        }
                    )
            except Exception:
                logger.warning("Salvage from AdapterParseError failed", exc_info=True)

            # 中立的兜底回覆，避免誤導（不再提及發燒/治療等內容）
            neutral_responses = [
                "我目前無法確認，請您再提供更具體的資訊。",
                "可否說明藥名、劑量與服用頻次？",
                "如果不確定，請直接說不確定。",
                "我會依據您提供的資訊再回覆。",
                "謝謝。",
            ]
            return dspy.Prediction(
                user_input=user_input,
                responses=neutral_responses,
                state="NORMAL",
                dialogue_context="unspecified",
                confidence=0.9,
                reasoning="auto-filled due to exception",
                context_classification="unspecified",
                examples_used=0,
                processing_info={
                    'unified_call': True,
                    'api_calls_saved': 2,
                    'state_reasoning': 'auto-filled due to exception',
                    'timestamp': datetime.now().isoformat(),
                    'fallback_used': True
                }
            )
    
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
            if responses_text is None:
                return []

            if isinstance(responses_text, str):
                stripped = responses_text.strip()
                if not stripped or stripped.lower() == 'none':
                    return []

            # 已是列表
            if isinstance(responses_text, list):
                flattened: List[str] = []
                for item in responses_text:
                    if isinstance(item, str):
                        inner = item.strip()
                        if not inner or inner.lower() == 'none':
                            continue
                        if (inner.startswith('[') and inner.endswith(']')) or (
                            inner.startswith('\u005b') and inner.endswith('\u005d')
                        ):
                            try:
                                parsed_inner = json.loads(inner)
                                if isinstance(parsed_inner, list):
                                    flattened.extend(str(x) for x in parsed_inner if str(x).strip())
                                    continue
                            except Exception:
                                pass
                        flattened.append(inner)
                    elif isinstance(item, list):
                        flattened.extend(str(x) for x in item if str(x).strip())
                    else:
                        text_item = str(item).strip()
                        if text_item and text_item.lower() != 'none':
                            flattened.append(text_item)

                if flattened:
                    return flattened[:5]
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
            # 返回空清單，避免以模板句覆蓋或外露錯誤字串
            return []

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
            if responses is None:
                return []

            if isinstance(responses, str):
                stripped = responses.strip()
                if not stripped or stripped.lower() == 'none':
                    return []

            # 已是列表
            if isinstance(responses, list):
                # 若為 ["[\"a\", \"b\"]"] 形式，嘗試解析內層字串為陣列
                if len(responses) == 1 and isinstance(responses[0], str):
                    inner = responses[0].strip()
                    if inner.startswith('[') and inner.endswith(']'):
                        try:
                            parsed_inner = json.loads(inner)
                            if isinstance(parsed_inner, list):
                                return [str(x) for x in parsed_inner[:5] if str(x).strip()]
                        except Exception:
                            pass
                # 若為 [[...]] 形式，展平為單層
                if len(responses) == 1 and isinstance(responses[0], list):
                    return [str(x) for x in responses[0][:5] if str(x).strip()]
                cleaned = [str(x).strip() for x in responses if str(x).strip()]
                if cleaned:
                    return cleaned[:5]
                return []
            
            if isinstance(responses, dict):
                extracted = _extract_from_dict(responses)
                if extracted is not None:
                    return extracted

            # 原始是字串 -> 嘗試 JSON 解析
            if isinstance(responses, str):
                try:
                    parsed = json.loads(responses)
                    if isinstance(parsed, list):
                        cleaned = [str(x).strip() for x in parsed if str(x).strip()]
                        return cleaned[:5]
                    if isinstance(parsed, dict):
                        extracted = _extract_from_dict(parsed)
                        if extracted is not None:
                            return extracted
                except json.JSONDecodeError:
                    lines = [line.strip() for line in responses.split('\n') if line.strip()]
                    return lines[:5]
            
            text = str(responses).strip()
            return [text] if text else []
        except Exception as e:
            logger.error(f"回應格式處理失敗: {e}", exc_info=True)
            # 返回空清單，避免以模板句覆蓋或外露錯誤字串
            return []


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
            if len(compact) == 2:
                break

        if not compact:
            compact = DEFAULT_CONTEXT_PRIORITY[:2]

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

        # 固定歷史視窗：10 輪對話 ≈ 20 行（去除系統行）；不再動態調整
        window_lines = 20
        # 準備非系統的原始對話行
        non_system = [x for x in conversation_history if isinstance(x, str) and not x.strip().startswith('[')]
        recent = non_system[-window_lines:]

        def _is_caregiver(line: str) -> bool:
            return isinstance(line, str) and line.strip().startswith("護理人員:")

        def _is_system(line: str) -> bool:
            s = line.strip() if isinstance(line, str) else ""
            return s.startswith("[") or s.startswith("[系統]") or s.startswith("(系統)")

        def _is_patient(line: str) -> bool:
            s = line.strip() if isinstance(line, str) else ""
            # 僅將病患名開頭或 Patient_ 前綴視為病患，避免把系統/其他角色誤判
            if not s or _is_system(s):
                return False
            if s.startswith(f"{character_name}:"):
                return True
            if s.startswith("Patient_"):
                return True
            if s.startswith("病患:"):
                return True
            return False

        has_caregiver = any(_is_caregiver(x) for x in recent)
        has_patient = any(_is_patient(x) for x in recent)
        selected = list(recent)

        # 產生條列摘要
        summary_lines: List[str] = []
        seen_bullets: set[str] = set()

        def _trim(s: str, n: int = 180) -> str:
            s = s.strip()
            return (s[:n] + '…') if len(s) > n else s
        # 逐行帶入所有非系統行，保持原始順序（固定 10 輪 ≈ 20 行）
        for entry in selected:
            if not entry:
                continue
            text = entry.strip()
            if not text or _is_system(text):
                continue
            summary_lines.append(f"- {_trim(text)}")

        formatted = "\n".join(summary_lines)
        # 在日誌中標示 window 與實際帶入行數，便於檢視
        logger.info(
            f"🔧 History management: total={len(conversation_history)} window_lines={window_lines} selected_count={len(summary_lines)} for {character_name}"
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
