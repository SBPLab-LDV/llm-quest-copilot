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
from dspy.adapters.utils import format_field_value
from dspy.dsp.utils.settings import settings

from .dialogue_module import DSPyDialogueModule
from .config import get_config
from ..scenario_manager import get_scenario_manager

logger = logging.getLogger(__name__)

JSON_OUTPUT_DIRECTIVE = (
    "[指示] 僅輸出單一 JSON 物件，包含欄位 context_classification, responses。"
    "必須維持合法 JSON 語法，所有鍵與值皆用雙引號。"
    "responses 必須是長度為 4 的 JSON 陣列；每個元素為一句簡短、自然、彼此獨立且互斥的完整繁體中文句子，"
    "且每句都需直接回應 user_input 的核心主題，不可偏題或答非所問。"
    "4 句需涵蓋不同的回應取向（例如：肯定、否定、不確定、提供具體但簡短的細節），"
    "禁止同義改寫或重覆語意，需更換不同名詞與動詞以確保差異化。"
    "二元問句和數值問句的詳細規則見 response_style_rules 欄位。"
    "嚴禁在 responses 中包含括號描述（肢體動作、表情）或與問題無關的模板句，只輸出病患實際說出口的話語。"
    "必須遵守上方提供的規則欄位（term_usage_rules、response_style_rules、persona_voice_rules）。"
    "【視角規範】所有回應必須以病患第一人稱表述，禁止醫護視角動詞（詢問/建議/安排/提醒/我們會）。"
    "【問題前提驗證】當問題中隱含的前提假設與 character_details 不符時，"
    "responses 應以病患視角質疑或澄清錯誤前提，禁止順著錯誤前提回答。"
    "禁止添加 [[ ## field ## ]]、markdown 或任何額外文字。"
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
    """統一的病患回應生成簽名（精簡提示 + 可優化規則欄位）。"""

    # 輸入欄位（核心語境）
    user_input = dspy.InputField(desc="對話方的問題")
    character_name = dspy.InputField(desc="病患姓名")
    character_persona = dspy.InputField(desc="病患性格")
    character_backstory = dspy.InputField(desc="病患背景")
    character_goal = dspy.InputField(desc="病患目標")
    character_details = dspy.InputField(desc="關鍵病情資訊")
    conversation_history = dspy.InputField(desc="近期對話與提醒")
    fewshot_examples = dspy.InputField(desc="回應格式示範範例")
    available_contexts = dspy.InputField(desc="候選情境")

    # 輸入欄位（可優化規則區塊：提供給 DSPy Optimizer 作為 prompt 片段）
    term_usage_rules = dspy.InputField(desc="用語規範（稱謂/職稱/敏感詞替換）")
    response_style_rules = dspy.InputField(desc="回應風格/多樣性/格式化規範")
    persona_voice_rules = dspy.InputField(desc="病患語氣與知識邊界規則")

    # 輸出欄位
    context_classification = dspy.OutputField(desc="情境分類 ID")
    responses = dspy.OutputField(desc="四個病患回應，嚴禁包含任何括號、動作描述、肢體語言或省略號（...），只輸出流暢完整的純口語句子")
    # 已移除：reasoning, core_question, prior_facts, context_judgement（僅 debug 用，改由 logger 記錄 LLM 原始輸出）



class UnifiedJSONAdapter(JSONAdapter):
    """Custom adapter that enforces JSON instructions without bracket markers."""

    def __init__(self, directive: str):
        super().__init__(use_native_function_calling=False)
        self.directive = directive.strip()

    def format_field_structure(self, signature: dspy.Signature) -> str:
        # 精簡：避免重覆列出指令與欄位型別，減少提示冗長
        return ""

    def user_message_output_requirements(self, signature: dspy.Signature) -> str:
        # 僅在主請求訊息尾端附加指令，這裡不再重覆
        return ""

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
        # 使用預設格式，避免再度枚舉欄位名稱與型別
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

        dspy_cfg = get_config().get_dspy_config()
        fewshot_cfg = dspy_cfg.get("fewshot", {}) or {}
        fast_mode_cfg = dspy_cfg.get("fast_mode", {}) or {}
        self._fewshot_enabled = bool(fewshot_cfg.get("enabled", True))
        self._fewshot_bootstrap_enabled = bool(fewshot_cfg.get("bootstrap_enabled", False))
        self._fewshot_max_examples = max(0, int(fewshot_cfg.get("max_examples", 2) or 2))
        self._fast_mode_enabled = bool(fast_mode_cfg.get("enabled", True))
        self._fast_reasoning_max_chars = max(40, int(fast_mode_cfg.get("reasoning_max_chars", 80) or 80))
        self._fast_response_max_chars = max(12, int(fast_mode_cfg.get("response_max_chars", 22) or 22))
        
        # 替換為統一的對話處理器：直接使用 Predict 並強制 JSONAdapter
        self.unified_response_generator = dspy.Predict(UnifiedPatientResponseSignature)
        self._json_adapter = UnifiedJSONAdapter(self._build_json_output_directive())

        # 預設規則片段（可被 Optimizer/設定覆蓋）
        # 用語規範：避免職稱稱呼；若不得不提，嚴禁「護士」，一律使用「護理師」。
        self._default_term_usage_rules = (
            "【用語規範】不用職稱稱呼對方；如需提及職稱，用『護理師』不用『護士』。"
        )
        # 數值問句專用風格規範（與 JSON_OUTPUT_DIRECTIVE 相輔相成；可被 Optimizer 覆寫）
        self._default_numeric_response_style_rules = (
            "【數值問句】若無確證不斷言數字；有確定數字則 1 句肯定引用；"
            "無確證時可提 2 個候選數字（印象/大概/可能修飾）。"
        )

        # 病患語氣與知識邊界規則：限制專業語氣與臆測，強化第一人稱感受表述
        self._default_persona_voice_rules = (
            "【病患視角】一律用第一人稱（我/我的），只描述自身的感受、困擾與日常線索；"
            "不得下指令安排檢查或治療，不對醫療流程提出專業建議。\n"
            "【知識邊界】不臆測醫囑、診斷、藥理或流程細節；若不確定，可直說不太確定，但整組回應中最多允許 1 句不確定，其餘需提供肯定/否定或具體但簡短的細節。\n"
            "【詞彙層級】優先使用生活語彙與身體感受詞（痛、刺、悶、腫、乾、想吐、吞嚥困難…）；"
            "需要提醫療名詞時，使用病患常見說法（如『止痛藥』『打點滴』），避免專業縮寫或術語。\n"
            "【不確定與求助】不確定句式總量上限 1；其餘句子提供實質內容，避免程序性說明。\n"
            "【句式風格】單句、簡短、自然；避免模板化與說教式表述；專注回應當前問題。"
        )

        # 一般問句的風格規範（避免過度『不確定』；優先引用歷史已知資訊）
        self._default_general_response_style_rules = (
            "【歷史優先】如對話歷史或角色設定中已有可引用的具體事實（藥名/劑量/頻次/時間/數字），至少在一個選項中直接且自然地引用，不得表達不確定。\n"
            "【二元問句策略】當 user_input 屬於『是否/有無/有沒有/…了嗎/…嗎』類二元問句時：\n"
            "- 必須至少 1 句『肯定/有』與 1 句『否定/沒有』；\n"
            "- 其餘 3 句用於：以不同語氣與側重提供具體但簡短的細節（避免流程/時間範圍/查驗程序的說明）；\n"
            "- 『不確定/記不清/再說一次』類句式總量上限 1。\n"
            "【內容多樣性】多樣性來自意圖/策略的互斥，而非同義改寫；避免僅換說法不換內容。\n"
            "【詞彙與語氣】單句、具體、自然、繁體中文；避免專業術語與說教口吻；以病患視角描述感受與需要。"
        )

        # 追蹤最近一次模型輸出情境，做為下輪提示濾器
        self._last_context_label: Optional[str] = None
        self._fewshot_used = False

        # 載入疼痛評估指引（啟動時載入一次，避免重複讀檔）
        self._pain_guide_context = self._load_pain_guide_context()

        # 初始化 ScenarioManager 用於動態載入 few-shot 範例
        try:
            self.scenario_manager = get_scenario_manager()
            logger.info(f"ScenarioManager 已載入 {len(self.scenario_manager.scenarios)} 個情境")
        except Exception as e:
            logger.warning(f"ScenarioManager 初始化失敗: {e}")
            self.scenario_manager = None

        # 簡化：一致性檢查停用
        self.enable_consistency_check = False
        
        # 統計信息
        self.unified_stats = {
            'api_calls_saved': 0,
            'total_unified_calls': 0,
            'success_rate': 0.0,
            'last_reset': datetime.now().isoformat()
        }
        
        logger.info(
            "UnifiedDSPyDialogueModule latency profile: fast_mode=%s, fewshot_enabled=%s, bootstrap_enabled=%s, fewshot_max=%s, response_max_chars=%s",
            self._fast_mode_enabled,
            self._fewshot_enabled,
            self._fewshot_bootstrap_enabled,
            self._fewshot_max_examples,
            self._fast_response_max_chars,
        )
        logger.info("UnifiedDSPyDialogueModule 初始化完成 - 已優化為單一 API 調用")

    def _build_json_output_directive(self) -> str:
        directive = JSON_OUTPUT_DIRECTIVE
        if not self._fast_mode_enabled:
            return directive
        return (
            f"{directive}\n"
            f"【低延遲輸出】每個 responses 句子不超過 {self._fast_response_max_chars} 字，避免贅語。"
        )

    def _load_pain_guide_context(self) -> str:
        """從 pain_assessment_guide.md 載入疼痛評估參考資訊

        這些資訊會注入 prompt，讓 LLM 在 self-annotation 時參考指引內容，
        生成符合臨床標準的疼痛相關回應。

        Returns:
            疼痛評估指引的 prompt 片段，若檔案不存在則返回空字串
        """
        from pathlib import Path

        guide_path = Path(__file__).parent.parent.parent.parent / "prompts/pain_assessment/pain_assessment_guide.md"

        if not guide_path.exists():
            logger.debug(f"疼痛評估指引檔案不存在: {guide_path}")
            return ""

        # 從指引中提取關鍵內容，轉換為 LLM 可參考的 prompt 片段
        # Phase 7: 臨床推理框架版本 - 連結治療階段與預期疼痛模式
        pain_guide = """[疼痛評估推理指引]

■ 推理步驟：
  1. 從 character_details 識別：診斷、治療階段、手術部位
  2. 根據治療階段推估預期疼痛程度：
     - 術後 1-3 天：中重度（4-7 分），傷口刺痛/脹痛
     - 術後 1-2 週：輕中度（2-5 分），逐漸緩解
     - 術後 1 個月以上：輕度或無痛（0-3 分）
     - 化療期間：黏膜炎疼痛，可能中度
     - 放療期間：照射部位灼熱感

■ 病患視角的疼痛描述對照：
  輕度(1-3分)：「有一點點」「還好」「可以忍受」「偶爾刺一下」
  中度(4-6分)：「蠻痛的」「有點難受」「會影響吃東西」「吃藥才能緩解」
  重度(7-10分)：「很痛」「受不了」「痛到睡不著」

■ 疼痛性質與情境對照：
  傷口痛（術後/換藥）：刺刺的、割割的、碰到會痛
  發炎痛（感染/黏膜炎）：腫腫的、脹脹的、熱熱的
  神經痛（神經損傷）：像電到、麻麻的、一陣一陣抽痛

■ 口腔癌術後常見：
  加重：吞嚥、張嘴、說話、碰觸傷口、換藥
  緩解：止痛藥、少說話、流質飲食、休息

■ 重要提醒：
  - 「止痛藥」專指止痛藥物（普拿疼、嗎啡類等），不包含抗生素（如阿莫西林）
  - 回應應符合 character_details 中的治療階段
  - 在 context_judgement.pain_assessment 中記錄推理過程

請根據上述指引，從病患視角生成符合其治療階段的疼痛描述。
"""
        logger.info("🩹 已載入疼痛評估指引")
        return pain_guide

    def _is_pain_related_query(self, user_input: str) -> bool:
        """檢查是否為疼痛相關問題

        使用擴展關鍵字列表確保不遺漏疼痛相關問題

        Args:
            user_input: 使用者輸入的問題

        Returns:
            True 如果問題涉及疼痛相關詞彙
        """
        pain_keywords = [
            "痛", "疼", "不舒服", "難受",  # 基本關鍵字
            "酸", "麻", "刺", "脹",         # 擴展關鍵字
        ]
        return any(kw in user_input for kw in pain_keywords)

    def forward(self, user_input: str, character_name: str, character_persona: str,
                character_backstory: str, character_goal: str, character_details: str,
                conversation_history: List[str]) -> dspy.Prediction:
        """統一的前向傳播 - 單次 API 調用完成所有處理
        
        Args:
            user_input: 對話方的輸入
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

            # 動態載入 few-shot 範例（基於上輪推理的情境）
            fewshot_section = ""
            self._fewshot_used = False
            if self._fewshot_enabled and self.scenario_manager:
                try:
                    # 第一輪對話：使用 bootstrap examples 確保多角色覆蓋
                    if self._last_context_label is None:
                        if self._fewshot_bootstrap_enabled:
                            examples = self.scenario_manager.get_bootstrap_examples()[:self._fewshot_max_examples]
                            logger.debug(f"📚 第一輪：載入 {len(examples)} 個 bootstrap 範例（多角色覆蓋）")
                        else:
                            examples = []
                            logger.debug("📚 第一輪：bootstrap few-shot 已停用")
                    else:
                        # 後續輪次：基於上輪情境載入範例
                        examples = self.scenario_manager.get_examples(
                            user_input=user_input,
                            previous_context=self._last_context_label,
                            max_examples=self._fewshot_max_examples,
                        )
                        logger.debug(f"📚 後續輪：載入 {len(examples)} 個情境範例 (context={self._last_context_label})")

                    if examples:
                        self._fewshot_used = True
                        fewshot_section = self.scenario_manager.format_examples_for_prompt(examples)
                except Exception as e:
                    logger.debug(f"Few-shot 載入失敗: {e}")
            elif not self._fewshot_enabled:
                logger.debug("📚 few-shot 已由設定停用")

            # 疼痛指引注入對話歷史（它是「提醒」性質，屬於 conversation_history）
            # 疼痛指引只在問題涉及疼痛時載入，減少非疼痛問題的 prompt 大小
            if self._pain_guide_context and self._is_pain_related_query(user_input):
                formatted_history = self._pain_guide_context + "\n\n" + formatted_history
                logger.info("🩹 檢測到疼痛相關問題，注入疼痛評估指引")
            elif self._pain_guide_context:
                logger.info("📝 非疼痛問題，跳過疼痛評估指引（節省 prompt 空間）")

            # few-shot 範例獨立傳遞，不混入 conversation_history（語意分離）
            fewshot_for_input = fewshot_section if fewshot_section else ""
            if fewshot_for_input:
                logger.debug(f"📚 Few-shot 範例獨立傳遞（長度: {len(fewshot_for_input)} 字元）")

            current_call = self.unified_stats['total_unified_calls'] + 1
            logger.info(f"🚀 Unified DSPy call #{current_call} - {character_name} processing {len(conversation_history)} history entries")
            
            # **關鍵優化：單一 API 調用完成所有處理**
            import time
            call_start_time = time.time()
            
            # 規則區塊可由設定覆寫（後續可擴充從 config 或 Optimizer 注入）
            term_rules = self._default_term_usage_rules
            # 依輸入意圖選用不同風格規則（數值問句 vs 一般問句）
            style_rules = (
                self._default_numeric_response_style_rules
                if self._is_numeric_query(user_input)
                else self._default_general_response_style_rules
            )
            if self._fast_mode_enabled:
                style_rules += (
                    f"\n【低延遲】responses 請維持短句，單句不超過 {self._fast_response_max_chars} 字，"
                    "避免重複與冗詞。"
                )
            persona_rules = self._default_persona_voice_rules

            with settings.context(adapter=self._json_adapter):
                unified_prediction = self.unified_response_generator(
                    user_input=user_input,
                    character_name=character_name,
                    character_persona=character_persona,
                    character_backstory=character_backstory,
                    character_goal=character_goal,
                    character_details=character_details,
                    conversation_history=formatted_history,
                    fewshot_examples=fewshot_for_input,
                    available_contexts=available_contexts,
                    term_usage_rules=term_rules,
                    response_style_rules=style_rules,
                    persona_voice_rules=persona_rules,
                )
            
            call_end_time = time.time()
            call_duration = call_end_time - call_start_time
            
            logger.info(f"✅ Call #{current_call} completed in {call_duration:.3f}s - {type(unified_prediction).__name__}")


            _preview = self._process_responses(unified_prediction.responses)[:3]
            _log_state = getattr(unified_prediction, 'state', 'UNKNOWN')
            logger.info(f"💬 Generated {len(_preview)} responses (preview) - State: {_log_state}")
            logger.info(f"📈 API calls saved: 2 (1 vs 3 original calls)")

            # 更新情境偏好，供下一輪精簡提示使用
            try:
                raw_context = getattr(unified_prediction, 'context_classification', None)
                normalized_context = self._normalize_context_label(raw_context)
                if normalized_context:
                    self._last_context_label = normalized_context
            except Exception:
                pass

            # Log LLM raw output fields for debug (no longer OutputFields)
            logger.info("context_classification: %s", getattr(unified_prediction, 'context_classification', ''))
            logger.info("responses_preview: %s", _preview)
            
            # 處理回應格式
            responses = self._process_responses(unified_prediction.responses)

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
                context_classification=_class,
                examples_used=0,
                processing_info={
                    'unified_call': True,
                    'api_calls_saved': 2,
                    'context_classification': _class,
                    'timestamp': datetime.now().isoformat(),
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
                        responses=[str(x).strip() for x in salv_responses if str(x).strip()][:4] or [
                            "語言模型伺服器超出限制，請聯繫管理人員。",
                            "語言模型伺服器超出限制，請聯繫管理人員",
                            "語言模型伺服器超出限制，請聯繫管理人員",
                            "語言模型伺服器超出限制，請聯繫管理人員",
                            "謝謝。",
                        ],
                        state="NORMAL",
                        dialogue_context=str(salvaged.get('dialogue_context') or 'unspecified'),
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
                "語言模型伺服器超出限制，請聯繫管理人員",
                "語言模型伺服器超出限制，請聯繫管理人員",
                "語言模型伺服器超出限制，請聯繫管理人員",
                "語言模型伺服器超出限制，請聯繫管理人員",
                "謝謝。",
            ]
            return dspy.Prediction(
                user_input=user_input,
                responses=neutral_responses,
                state="NORMAL",
                dialogue_context="unspecified",
                context_classification="unspecified",
                examples_used=0,
                processing_info={
                    'unified_call': True,
                    'api_calls_saved': 2,
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
                return [str(x) for x in candidate[:4]]
            if isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:4]]
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
                    return flattened[:4]
                return [str(x) for x in responses_text[:4]]

            if isinstance(responses_text, dict):
                extracted = _extract_from_dict(responses_text)
                if extracted is not None:
                    return extracted

            # 原始是字串 -> 嘗試 JSON 解析
            if isinstance(responses_text, str):
                try:
                    parsed = json.loads(responses_text)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:4]]
                    if isinstance(parsed, dict):
                        extracted = _extract_from_dict(parsed)
                        if extracted is not None:
                            return extracted
                except json.JSONDecodeError:
                    # 不是 JSON，按行分割
                    lines = [line.strip() for line in responses_text.split('\n') if line.strip()]
                    return lines[:4]
            
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
                return [str(x) for x in candidate[:4]]
            if isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed[:4]]
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
                                return [str(x) for x in parsed_inner[:4] if str(x).strip()]
                        except Exception:
                            pass
                # 若為 [[...]] 形式，展平為單層
                if len(responses) == 1 and isinstance(responses[0], list):
                    return [str(x) for x in responses[0][:4] if str(x).strip()]
                cleaned = [str(x).strip() for x in responses if str(x).strip()]
                if cleaned:
                    return cleaned[:4]
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
                        return cleaned[:4]
                    if isinstance(parsed, dict):
                        extracted = _extract_from_dict(parsed)
                        if extracted is not None:
                            return extracted
                except json.JSONDecodeError:
                    lines = [line.strip() for line in responses.split('\n') if line.strip()]
                    return lines[:4]
            
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
        window_lines = 10
        # 準備非系統的原始對話行
        non_system = [x for x in conversation_history if isinstance(x, str) and not x.strip().startswith('[')]
        recent = non_system[-window_lines:]

        def _is_caregiver(line: str) -> bool:
            return isinstance(line, str) and line.strip().startswith("對話方:")

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

    # ------------------------------------------------------------------
    # Intent utilities
    # ------------------------------------------------------------------
    def _is_numeric_query(self, text: str) -> bool:
        """粗略偵測是否為數值/計量相關問句。

        避免沉重 NLU；使用高召回率的關鍵詞啟發（中文常見量詞/疑問詞）。
        """
        if not isinstance(text, str):
            return False
        s = text.strip()
        if not s:
            return False
        # 觸發詞：幾、多少、幾次、幾罐、幾盒、幾顆、幾片、幾毫升、幾公克、幾點、幾天...
        keywords = [
            "幾", "多少", "幾次", "幾罐", "幾瓶", "幾袋", "幾顆", "幾片", "幾毫升", "幾公克",
            "幾點", "幾天", "幾週", "幾個", "幾項", "幾人", "幾號",
        ]
        # 量詞/數字圖樣：阿拉伯數字 + 量詞（罐/瓶/袋/次）也可視作數值意圖
        import re
        if any(k in s for k in keywords):
            return True
        if re.search(r"\d+\s*(罐|瓶|袋|次|顆|片|毫升|公克)", s):
            return True
        return False
    
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
