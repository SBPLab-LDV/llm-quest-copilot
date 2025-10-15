Here’s a precise mapping from the PDF issues to the current DSPy Signatures/Modules, with code references, plus latent (non‑directly observable) factors that likely drive the reported failures. I separate “口語表達” and “文字回答” paths, then call out shared contributors.

Modules In Scope
- 口語表達 pipeline
  - Prompt composition: `AudioPromptComposerModule` with `AudioDisfluencyChatSignature` (system/user prompt assembly) in src/core/dspy/audio_modules.py
  - System prompt template: prompts/templates/audio_disfluency_template.yaml
  - Gemini multimodal call and JSON cleanup: src/llm/gemini_client.py
  - Normalization to {original, options}: `AudioDisfluencyPostModule.normalize` in src/core/dspy/audio_modules.py
  - UI mapping: “請選擇您想表達的內容” in src/ui/app.py
- 文字回答 pipeline
  - Dialogue manager: `OptimizedDialogueManagerDSPy` (uses unified DSPy module) in src/core/dspy/optimized_dialogue_manager.py
  - Unified response generator: `UnifiedDSPyDialogueModule` with `UnifiedPatientResponseSignature` in src/core/dspy/unified_dialogue_module.py
  - JSON output directive and style rules: src/core/dspy/unified_dialogue_module.py
  - Legacy signature (older non‑unified path): `PatientResponseSignature` in src/core/dspy/signatures.py
  - UI mapping: “病患回應選項” in src/ui/app.py

口語表達（ASR→句子選項）
- 問題類型 → 直接對應與原因
  - 只辨識片段、意圖遺失（例：嗆..到..回...家 只讀到回家）
    - Where it happens:
      - Multimodal LLM is asked to both “理解”與“正規化”而非純轉錄，無額外 VAD/斷句/補全層 src/llm/gemini_client.py
      - 後處理僅做 JSON 清理，不做語義補全 src/core/dspy/audio_modules.py
    - Why (latent):
      - Prompt側要求直接輸出 options，缺少“意圖覆蓋/關鍵詞保全”規範；系統不做多段合併/容錯（非觀測因素）
  - 選項語氣過專業、不像病人口語
    - Where:
      - 模板明確指示「優先使用醫療場景與專有名詞」 prompts/templates/audio_disfluency_template.yaml
    - Why:
      - 模板語氣偏醫療專業，與測試期望“病人口語”相違
  - 情境不符（門診卻生成住院/出院情境）
    - Where:
      - 模板硬編入「正在住院中」 prompts/templates/audio_disfluency_template.yaml
      - 僅帶入2個高優先情境（預設） src/core/audio/context_utils.py
    - Why:
      - 口語表達固定假設住院場域→門診案例產生“想出院”等錯位選項
  - 多意圖未被覆蓋（同一句含“痛＋睡不著”只覆蓋其中一個）
    - Where:
      - `AudioDisfluencyChatSignature`與模板未定義“multi‑intent coverage”或 per‑intent 槽位 src/core/dspy/signatures.py
    - Why:
      - 無“每個意圖至少一個選項”的硬約束；LLM取最顯著意圖生成

- 關鍵設計與配置（影響質變）
  - 組裝提示採 DSPy（可切 legacy），DSPy分離 system/user prompt（利於維護） src/llm/gemini_client.py
  - 模板規則文字由 `build_audio_template_rules` 嵌入，但也未包含多意圖/限制檢核 src/core/audio/context_utils.py

文字回答（醫護問句→病患回應選項）
- 問題類型 → 直接對應與原因
  - 違反臨床限制（ICU 舌癌術後仍出現可說話、可吞嚥、可下床、可口進食等）
    - Where (data not carried):
      - `UnifiedPatientResponseSignature` 無 can_speak、swallowing_status、feeding_route、mobility 等欄位 src/core/dspy/unified_dialogue_module.py
      - 將 details 當成一坨文本/字典塞給 `character_details`，未結構化成限制條件 src/core/dspy/optimized_dialogue_manager.py
    - Where (no enforcement):
      - JSON 指令未要求“臨床禁忌護欄/選項過濾” src/core/dspy/unified_dialogue_module.py
      - 一致性檢查關閉（無前後事實護欄） src/core/dspy/unified_dialogue_module.py
    - Why:
      - LLM 缺乏顯式限制欄位與“禁止清單”→容易產生不可能/不安全選項（非觀測）
  - 前後文矛盾（先說不痛，後續選項又說傷口痛）
    - Where:
      - 歷史以條列原句拼接，無“事實抽取/狀態記憶/矛盾檢查” src/core/dspy/unified_dialogue_module.py
      - few‑shot 被刻意移除以縮短提示 src/core/dspy/unified_dialogue_module.py
      - 一致性檢查停用 src/core/dspy/unified_dialogue_module.py
    - Why:
      - 歷史僅作為“長文本參考”，未凝練成“已知事實”供邏輯硬約束；無矛盾過濾（非觀測）
  - 答非所問（例：問第幾次放療，卻回副作用）
    - Where:
      - JSON 指令強調“多樣性/五槽位”，缺乏“直接回應提問核心”的 check src/core/dspy/unified_dialogue_module.py
      - 無“question_focus/answer_directness”欄位；未使用 few‑shot引導精準回答 src/core/dspy/unified_dialogue_module.py
    - Why:
      - 模型發散生成，缺少“核心問答對焦”硬規範
  - 情境錯置（未化療卻談化療）
    - Where:
      - 統一模組未用 example bank few‑shot；情境僅提供“候選情境字串” src/core/dspy/unified_dialogue_module.py
      - 日誌顯示 example bank 回退至“簡單文本相似度”（嵌入缺席），對早期非統一路徑也會弱化情境擷取
    - Why:
      - 缺乏強化情境的 few‑shot 與限制欄位，致語義漂移

- 關鍵設計與配置（影響質變）
  - `JSON_OUTPUT_DIRECTIVE`追求“5句多樣化”，而非“臨床/提問約束優先” src/core/dspy/unified_dialogue_module.py
  - 數值問句的“候選數字策略”會誘發“臆測數據樣式”（若輸入近似數量提問） src/core/dspy/unified_dialogue_module.py
  - 對話歷史僅加上 persona reminder，但不轉成“事實存儲/黑名單” src/core/dspy/unified_dialogue_module.py

跨模組的潛在（不可直接觀測）因子
- Few‑shot撤除與檢核關閉
  - 在統一模組中關閉 few‑shot與一致性檢查，明顯降低“語境對齊”與“邏輯一致性” src/core/dspy/unified_dialogue_module.py
- 檢索弱化
  - 日誌顯示 example bank 嵌入缺席而退化為表面相似度，前一代路徑的情境/範例匹配本就弱
- 音訊識別策略
  - 以多模態 LLM 直接“理解+改寫”，無前置 ASR/VAD/片段合併/錯誤更正；容錯與保真不足 src/llm/gemini_client.py
- 模板與規則導向
  - 口語表達模板硬性“住院”與“專有名詞優先”→導致門診錯位與過專業語氣 prompts/templates/audio_disfluency_template.yaml
- 未顯式化的臨床限制
  - 模組間傳遞的是“描述性 details”，不是“可執行限制欄位”，無法形成生成前/後的硬過濾 src/core/dspy/unified_dialogue_module.py, src/core/dspy/optimized_dialogue_manager.py

為何這些因子會導致測試觀察到的失敗
- 口語表達
  - 模板先驗“住院環境”+“專業語彙偏好”→在門診案例產生“想出院/流程化/專業化”選項
  - 無多意圖覆蓋約束→複合詞（痛＋睡不著）僅覆蓋其一
  - 無 ASR 清洗與關鍵詞保全→“嗆到”被丟失，只剩“回家”
- 文字回答
  - 無顯式限制（能否說話/吞嚥/下床/口進食）+ 無安全/一致性檢核→產生不可能/不安全/矛盾選項
  - 少了 few‑shot 與“直接回答核心”欄位→易發散成副作用或無關描述
  - 情境提示僅是“候選情境字串”，沒有可執行邏輯→化療/門診/ICU 等場景約束沒落地

簡要映射（測試回饋 → 模塊/原因）
- ASR 只辨識片段、意圖遺失 → 口語表達：多模態生成無容錯層與多意圖策略 src/llm/gemini_client.py, src/core/dspy/audio_modules.py
- 選項過專業、不像病人 → 口語表達：模板鼓勵專有名詞 prompts/templates/audio_disfluency_template.yaml
- 門診/住院情境錯位 → 口語表達：硬編“住院” prompts/templates/audio_disfluency_template.yaml
- ICU 限制違反（可說話/吞嚥/下床/口進食） → 文字回答：無限制欄位與安全過濾 src/core/dspy/unified_dialogue_module.py
- 前後文矛盾 → 文字回答：歷史未結構化、few‑shot關閉、一致性關閉 src/core/dspy/unified_dialogue_module.py
- 答非所問 → 文字回答：JSON 指令偏多樣性，未要求 directness 檢核 src/core/dspy/unified_dialogue_module.py
- 化療情境錯置 → 文字回答：缺 few‑shot、檢索弱化、情境僅字串提示

要我把這些觀察轉成最小修改的 DSPy 方案（不新增複雜自定義程式）：例如
- 為 UnifiedPatientResponseSignature 增加結構欄位 `can_speak`, `swallowing_status`, `feeding_route`, `mobility_level`, `allowed_actions`, `forbidden_actions` 並在 JSON 指令中要求嚴格遵守；
- 在音訊模板移除“正在住院中”，改成由角色浮動設定推導；新增“多意圖至少一項覆蓋”的簡短規則；
- 在 unified 模組增加 `answer_directness` 與 `scenario_fit` 的輸出要求，配合 JSONAdapter 做最小 post-check 過濾；
- 重啟少量 few‑shot（1–2 條）且控制長度；

我可以先起草簽名與 JSON 指令片段，仍符合「DSPy First & Prompt-based」原則，供你直接試跑。

