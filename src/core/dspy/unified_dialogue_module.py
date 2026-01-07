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
from ..scenario_manager import get_scenario_manager

logger = logging.getLogger(__name__)

JSON_OUTPUT_DIRECTIVE = (
    "[指示] 僅輸出單一 JSON 物件，包含欄位 reasoning, context_classification, responses, core_question, prior_facts, context_judgement。必須維持合法 JSON 語法，"
    "所有鍵與值皆用雙引號，禁止輸出 None/null/True/False 或未封閉的字串。不得輸出任何分析或思考步驟，"
    "請直接輸出 JSON 物件（不要附加除 JSON 以外的文字）。reasoning 請簡短說明如何產生這 4 句回應。"
    "responses 必須是一個長度為 4 的 JSON 陣列；每個元素為一句簡短、自然、彼此獨立且互斥的完整繁體中文句子，"
    "且每句都需直接回應 user_input 的核心主題，自然提及相關詞彙，不可偏題或答非所問。"
    "4 句需涵蓋不同的回應取向（例如：肯定、否定、不確定、提供具體但簡短的細節），"
    "禁止同義改寫或重覆語意，需更換不同名詞與動詞以確保差異化。"
    "若 user_input 為是否/有無/有沒有/…了嗎/…嗎 類二元問句，必須至少包含 1 句『肯定/有』與 1 句『否定/沒有』；"
    "其餘 2 句可呈現不同語氣與側重，提供具體但簡短的細節（避免冗長解釋與流程說明）。"
    "若 user_input 為數值/計量問句（含『幾/多少/幾瓶/幾次/幾毫升…』），四句中可包含：\n"
    "- 『肯定數字』：僅在歷史/設定有明確事實時才直接引用該數字；\n"
    "- 『候選數字』：以『印象/大概/可能』修飾不同的小整數候選（如 1 或 2）；\n"
    "- 其餘句子以不同語氣與側重提供簡短細節，避免流程性說明。\n"
    "不確定/記不清/再說一次 類句式最多允許 1 句；其餘句子提供實質內容。"
    "嚴禁在回覆或生成過程中計算或提及字數；嚴禁描述規則、分析或英文內容；嚴禁在 responses 中包含任何括號描述（如肢體動作、表情或舞台指示），只輸出病患實際說出口的話語；"
    "嚴禁輸出與當前問題無關的模板句（如客套語、表態語）除非問題明確在問該事項。"
    "『數字/時間』不得臆測的限制僅適用於肯定數字或時間值；允許以『候選』形式提出不同數字供選。『有/沒有』的二元選項仍須同時產生以提供選擇。"
    "禁止添加 [[ ## field ## ]]、markdown 或任何額外文字，完整輸出後以 } 結束。"
    "responses 必須為 JSON 陣列（雙引號字串的陣列），不可加整段引號或使用 Python list 表示法（不得使用單引號）。"
    "必須遵守上方提供的規則欄位（例如 term_usage_rules、response_style_rules、persona_voice_rules）。"
    "\n\n[欄位定義 - 必須包含]\n"
    "- core_question: 對 user_input 的核心重述，簡短自然的片語或短句。\n"
    "- prior_facts: 與本次回答最相關的事實陣列（最多 3 條，簡短片語），來源於 character_details 與 conversation_history；"
    "  至少嘗試包含 1 條源自最近對話視窗的事實；若近期對話沒有合適事實，請不要硬湊或臆造，可僅列出 character_details 的事實。\n"
    "- context_judgement: 物件，包含：\n"
    "  premise_check: 問題前提驗證，包含 question_assumes、medical_facts、match(bool)、mismatch_detail(可選)；\n"
    "  pain_assessment: 若涉及疼痛則填寫 is_pain_related、intensity_hint（可選）。\n"
    "【視角規範】所有回應必須以病患第一人稱表述，禁止醫護視角動詞（詢問/建議/安排/提醒/我們會）。\n"
    "所有 responses 必須與 context_judgement 的推論一致。\n"
    "【問題前提驗證】當問題中隱含的前提假設與 character_details 不符時：\n"
    "- premise_check.match 必須設為 false；\n"
    "- responses 應以病患視角質疑或澄清錯誤前提，指出實際病歷事實；\n"
    "- 禁止順著錯誤前提回答，必須先澄清事實。"
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
    available_contexts = dspy.InputField(desc="候選情境")

    # 輸入欄位（可優化規則區塊：提供給 DSPy Optimizer 作為 prompt 片段）
    term_usage_rules = dspy.InputField(desc="用語規範（稱謂/職稱/敏感詞替換）")
    response_style_rules = dspy.InputField(desc="回應風格/多樣性/格式化規範")
    persona_voice_rules = dspy.InputField(desc="病患語氣與知識邊界規則")

    # 輸出欄位（必填）
    reasoning = dspy.OutputField(desc="推理與一致性檢查")
    context_classification = dspy.OutputField(desc="情境分類 ID")
    responses = dspy.OutputField(desc="四個病患回應，嚴禁包含任何括號、動作描述、肢體語言或省略號（...），只輸出流暢完整的純口語句子")
    # 推薦輸出：便於後處理與審核
    core_question = dspy.OutputField(desc="對問題核心的簡短重述")
    prior_facts = dspy.OutputField(desc="最多三條相關事實")
    context_judgement = dspy.OutputField(desc="情境自由推理與生成方針")
    # 已移除：character_consistency_check, confidence, meta_summary（僅 debug 用，減少 LLM 輸出 tokens）



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
        
        # 替換為統一的對話處理器：直接使用 Predict 並強制 JSONAdapter
        self.unified_response_generator = dspy.Predict(UnifiedPatientResponseSignature)
        self._json_adapter = UnifiedJSONAdapter(JSON_OUTPUT_DIRECTIVE)

        # 預設規則片段（可被 Optimizer/設定覆蓋）
        # 用語規範：避免職稱稱呼；若不得不提，嚴禁「護士」，一律使用「護理師」。
        self._default_term_usage_rules = (
            "【用語規範】回應不得以職稱稱呼對方；避免使用如『醫師』『護理師』等稱謂。"
            "若不得不提職稱，嚴禁使用『護士』，一律使用『護理師』稱呼。"
        )
        # 數值問句專用風格規範（與 JSON_OUTPUT_DIRECTIVE 相輔相成；可被 Optimizer 覆寫）
        self._default_numeric_response_style_rules = (
            "【數值回答政策】\n"
            "- 嚴禁將不實數字包裝為事實；若無確證，不要斷言具體數字。\n"
            "- 若有確定數字，僅在 1 句中以肯定語氣提供；不得把同一數字換句話說以湊多樣性。\n"
            "- 在無確證時，允許提出 2 個『候選數字』，需以『印象/大概/可能』修飾。\n"
            "- 五句應呈現互斥意圖：肯定數字（若有）/ 候選#1 / 候選#2 / 其他具體但簡短的細節 / 不確定（最多 1 句）。\n"
            "- 二元『有/沒有』不受此數字臆測限制；可在候選或釐清語句中自然帶出。\n\n"
            "【五槽位多樣性】（五句各取其一，不得重覆）\n"
            "【格式/語氣】\n"
            "- 單句、具體、自然、繁體中文；五句互不重覆，意圖取向不同。\n"
            "- 避免模板化或空泛表述；『不確定/不太記得/能不能再說一次』等不確定語氣最多允許出現 1 次；其餘句子須提供具體內容（候選數字+修飾詞或其他簡短細節）。"
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
        self._last_pain_assessment: Optional[Dict[str, Any]] = None  # 追蹤疼痛評估結果
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
        
        logger.info("UnifiedDSPyDialogueModule 初始化完成 - 已優化為單一 API 調用")

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
        # 注意：這裡不直接讀取整份檔案，而是提供結構化的摘要
        pain_guide = """[疼痛評估參考指引]
來源：prompts/pain_assessment/pain_assessment_guide.md

■ 疼痛程度分級（0-10 數字量表）：
  - 0 分：完全不痛
  - 1-3 分：輕度疼痛，可以忍受，不太影響日常
  - 4-6 分：中度疼痛，有點影響日常活動
  - 7-10 分：重度疼痛，很難忍受

■ 疼痛性質詞彙（病患常用說法）：
  刺痛/刺刺的、刀割痛、鈍痛/悶悶的、抽痛/一陣一陣、
  壓痛/脹脹的、燒灼痛/熱熱的、酸痛/酸酸的

■ 常見加重因素：
  碰觸傷口、翻身移動、下床活動、吞嚥/吃東西、咳嗽、換藥

■ 常見緩解方式：
  吃止痛藥、躺著不動、熱敷、冷敷、舒適擺位（墊高）、深呼吸

若問題涉及疼痛，請在 context_judgement.pain_assessment 中根據上述指引和病患狀況進行推理。
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
            if self.scenario_manager:
                try:
                    # 第一輪對話：使用 bootstrap examples 確保多角色覆蓋
                    if self._last_context_label is None:
                        examples = self.scenario_manager.get_bootstrap_examples()
                        logger.debug(f"📚 第一輪：載入 {len(examples)} 個 bootstrap 範例（多角色覆蓋）")
                    else:
                        # 後續輪次：基於上輪情境載入範例
                        examples = self.scenario_manager.get_examples(
                            user_input=user_input,
                            previous_context=self._last_context_label,
                            max_examples=3
                        )
                        logger.debug(f"📚 後續輪：載入 {len(examples)} 個情境範例 (context={self._last_context_label})")

                    if examples:
                        fewshot_section = self.scenario_manager.format_examples_for_prompt(examples)
                except Exception as e:
                    logger.debug(f"Few-shot 載入失敗: {e}")

            # 將疼痛指引和 few-shot 範例注入對話歷史
            # 疼痛指引只在問題涉及疼痛時載入，減少非疼痛問題的 prompt 大小
            context_additions = []
            if self._pain_guide_context and self._is_pain_related_query(user_input):
                context_additions.append(self._pain_guide_context)
                logger.info("🩹 檢測到疼痛相關問題，注入疼痛評估指引")
            elif self._pain_guide_context:
                logger.info("📝 非疼痛問題，跳過疼痛評估指引（節省 prompt 空間）")
            if fewshot_section:
                context_additions.append(fewshot_section)

            if context_additions:
                formatted_history = "\n\n".join(context_additions) + "\n\n" + formatted_history
                logger.debug(f"📋 已注入 {len(context_additions)} 個 context additions")

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

            # 從 context_judgement 中提取 pain_assessment（用於追蹤和品質監控）
            try:
                ctx_judge = getattr(unified_prediction, 'context_judgement', None)
                if ctx_judge:
                    if isinstance(ctx_judge, str):
                        ctx_judge = json.loads(ctx_judge)
                    if isinstance(ctx_judge, dict):
                        pain_assessment = ctx_judge.get('pain_assessment')
                        if pain_assessment:
                            self._last_pain_assessment = pain_assessment
                            is_pain = pain_assessment.get('is_pain_related', False)
                            if is_pain:
                                logger.debug(f"🩹 Pain assessment: intensity={pain_assessment.get('intensity_hint')}, "
                                           f"quality={pain_assessment.get('quality_hints')}")
            except Exception as e:
                logger.debug(f"Failed to extract context_judgement fields: {e}")

            # Detailed reasoning and fields for inspection
            try:
                logger.info("=== UNIFIED REASONING OUTPUT ===")
                logger.info(f"reasoning: {getattr(unified_prediction, 'reasoning', '')}")
                logger.info(f"character_consistency_check: {getattr(unified_prediction, 'character_consistency_check', '')}")
                logger.info(f"context_classification: {getattr(unified_prediction, 'context_classification', '')}")
                logger.info(f"confidence: {getattr(unified_prediction, 'confidence', '')}")
                logger.info(f"dialogue_context: {getattr(unified_prediction, 'dialogue_context', '')}")
                logger.info(f"state_reasoning: {getattr(unified_prediction, 'state_reasoning', '')}")
                logger.info(f"core_question: {getattr(unified_prediction, 'core_question', '')}")
                logger.info(f"prior_facts: {getattr(unified_prediction, 'prior_facts', '')}")
                logger.info(f"context_judgement: {getattr(unified_prediction, 'context_judgement', '')}")
                logger.info(f"meta_summary: {getattr(unified_prediction, 'meta_summary', '')}")
                # Show up to first 3 responses for brevity
                logger.info(f"responses_preview: {_preview}")
            except Exception:
                pass
            
            # 處理回應格式
            responses = self._process_responses(unified_prediction.responses)

            # 簡化：一致性檢查已停用
            consistency_info = None
            
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
                context_judgement=getattr(unified_prediction, 'context_judgement', None),  # 傳遞 context_judgement 以便提取 inferred_speaker
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
                        responses=[str(x).strip() for x in salv_responses if str(x).strip()][:4] or [
                            "語言模型伺服器超出限制，請聯繫管理人員。",
                            "語言模型伺服器超出限制，請聯繫管理人員",
                            "語言模型伺服器超出限制，請聯繫管理人員",
                            "語言模型伺服器超出限制，請聯繫管理人員",
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
