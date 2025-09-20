# 對話歷史管理改進方案（依據 dialogue_history_management_analysis.md 實證對照）

## 摘要
- 目前專案的對話歷史管理與 DSPy 整合已具備雛形（統一模組、8 輪歷史策略、規則式一致性檢查），但仍存在數個實務落差：
  1) Prompt 中 `character_details` 遺漏（先前為 `{}`），降低多輪理解力。
  2) 歷史僅有護理人員發言，欠缺「病患回應」的回寫，使第二輪後語境不足。
  3) API 層偶發將 5 個回應包成「單一字串列表」造成 single_response 假警報。
  4) 伺服器層 CONFUSED fallback 曾注入「自我介紹」與單一回應，與一致性原則衝突。
  5) `dialogue_module.py` 多步驟實作與 Unified 並存，工程複雜度偏高。
  6) ExampleSelector/範例機制利用有限，無法做語義補強。
- 已完成修復：1/2/3/4（詳述於「已落地修復」）。
- 本計畫提出短中長期改進的可執行路線圖與 To‑Do。

---

## 問題對照（與 dialogue_history_management_analysis.md 一致）

### 1) Prompt 中 `character_details` 遺漏
- 現象：Gemini Prompt 的 `[[ ## character_details ## ]]` 先前經常為 `{}`，使模型少關鍵背景。
- 根因：對話管理器從未優先取 `Character.details`。改為讀取 `self.character.details` 後，prompt 注入正確 JSON。
- 現況：已修復（見「已落地修復」）。

### 2) 歷史雙方回寫不足
- 現象：`conversation_history` 僅持續追加「護理人員: …」，缺少「病患: …」，導致多輪上下文「單邊」。
- 現況：已在 GUI / API 回路中，每輪將 AI 首選回應回寫為「病患: …」，讓後續 prompt 有「雙方對話」。

### 3) 單回應假警報（"single_response" artifact）
- 現象：API 返回 `responses` 可能為 `['["a","b",…]']`（單元素字串化列表），評測誤認為 1 條回應。
- 現況：已在 API server 的 `format_dialogue_response()` 正規化 `responses`，解析字串化列表、字串多行，保證最終為 `List[str]`。

### 4) 伺服器 fallback 注入自我介紹/單回應
- 現象：上游 CONFUSED 時 server 注入「您好，我是…」等模板 + 單回應。
- 現況：已改為 5 條中性醫療回應（無自我介紹），同時維持 NORMAL 狀態，避免與一致性衝突。

### 5) `dialogue_module.py` 與 Unified 並存（過度工程化）
- 現象：多步驟（分類→範例→生成→狀態）與 Unified（單調用）同時存在，維護成本升高。
- 建議：將 Unified 作為缺省實現，逐步「凍結」多步驟路徑（保留但不活躍），文件與設定明確標注。

### 6) 範例/ExampleSelector 利用不足
- 現象：有 ExampleSelector，但回應生成 prompt 尚未穩健插入 few‑shot，對冷啟/稀疏上下文支援不足。
- 建議：加一層「語義檢索 → few‑shot 拼接」管線，或用 DSPy ExampleBank 自動召回最相關樣例插入 prompt。

---

## 已落地修復（Commit 對照）

- `character_details` 注入：
  - `src/core/dspy/optimized_dialogue_manager.py: _get_character_details()`
  - `src/core/dspy/dialogue_manager_dspy.py: _get_character_details()`

- 對話歷史回寫（病患）：
  - `src/core/dspy/optimized_dialogue_manager.py: _handle_gui_mode()`
  - `src/core/dspy/dialogue_manager_dspy.py: _handle_gui_mode()`

- API responses 正規化：
  - `src/api/server.py:546–580`（解析 `['a','b']` 字串化列表，或單字串按行拆分）

- Server CONFUSED fallback 中性化：
  - `src/api/server.py:600+`（5 條中性醫療回應、無自我介紹、state 改 NORMAL）

- 記錄完善：
  - `dspy_internal_debug.log`：完整 Prompt/Response、Unified 推理欄位
  - `api_server.log`：SERVER_FALLBACK_TRIGGERED / ORIGINAL 診斷標記

---

## 具體案例（前後對照）

- 先前（問題樣式）
  - Prompt：`character_details` 為 `{}`；history 為「護理人員: …」連續數條
  - Response：`{"responses":["抱歉，我現在無法正確回應"],"state":"CONFUSED"}` → server 注入自我介紹單回應

- 現在（修復後）
  - Prompt：包含 `name/persona/backstory/goal/details` 與「病患: …」歷史行
  - Response：
    ```json
    {
      "reasoning":"病房日常；角色一致；邏輯檢查…",
      "context_classification":"daily_routine_examples",
      "responses":["還可以…","今天精神好一些…","…"],
      "state":"NORMAL",
      "dialogue_context":"病房日常對話…"
    }
    ```
  - API 返回：`responses` 為 5 條 `List[str]`，不再出現單元素字串化列表。

---

## 改進方案（Roadmap）

### Phase A（立即）
1. 將 Unified 設為缺省實現（config 層面清楚標註），在文件中標示 `dialogue_module.py` 為 legacy 路徑（保留以備回退）。
2. 在 Unified module 增加可選的 ExampleBank few‑shot 拼接（k=2~3；成本增量可控），以補冰冷上下文。
3. 在 `processing_info` 中回傳 `consistency` 摘要（已存在於 Unified 內部），於 API 層透傳供排查。

### Phase B（短期 1–2 週）
1. 歷史管理語義加權：
   - 在 `_get_enhanced_conversation_history()` 內加入「關鍵詞/症狀/事件」權重，保留關鍵事實 + 最近輪，總長不超 8 輪；超限則做事實摘要一行化。
2. 規則式一致性擴展：
   - 增加更多醫療事實維度（用藥依從性、飲食、睡眠、活動耐受度）。
   - 時間線檢查加入同義時間詞（如「清晨 / 午夜 / 早上」）。
3. Server 層 JSONL 世代日誌（可選）：
   - 每次回覆輸出一行 JSON 指標（ts、session、context_classification、state、responses_count、flags），便於線上觀測。

### Phase C（中期 3–6 週）
1. Summarizer 簽名（可選、toggle）：
   - 新增 `ConversationSummarySignature`，當歷史超長或雜訊過多時產製「結構化摘要」並用於下一輪的 `conversation_history` 字段（替代堆疊）。
2. 自動 few‑shot 最佳化：
   - 使用簡易相似度（或現有 ExampleBank 的索引）在回合內自適應選例，定期更新 ExampleBank。
3. 減少多實現分歧：
   - 文件與 Config 中將 `optimized` 視作預設主線，`basic/legacy` 僅作 fallback；CI 中跑 smoke 測，避免漂移。

---

## To‑Do List（可勾選）

- [ ] Config / README：標示 Unified 為缺省，legacy 標籤加註。
- [ ] Unified：插入 ExampleBank few‑shot（k=2~3），量測回應穩定性/延遲。
- [ ] Unified → API：透傳 `processing_info.consistency`（可由 server 打印/回傳）。
- [ ] `_get_enhanced_conversation_history()`：加入語義關鍵字保留策略，壓縮非關鍵輪。
- [ ] ConsistencyChecker：擴充醫療事實（服藥、飲食、睡眠、活動、情緒）。
- [ ] ConsistencyChecker：時間線詞彙擴展（清晨/中午/傍晚/午夜）。
- [ ] 觀測：新增 `logs/dialogue_events.jsonl`（每回一行）便於線上監控。
- [ ] Summarizer 簽名（可選）：behind a toggle，不增加現階段 API 成本。
- [ ] CI：對 legacy 與 optimized 都跑最小自動測試，避免回歸。

---

## 風險與緩解
- 範例拼接可能增加回應時延：控制 k ≤ 3；必要時只在低分回合或「語境不足」時觸發。
- 歷史語義加權可能誤刪關鍵事實：採「關鍵詞白名單 + 最近輪」雙門檻。
- Summarizer 引入 LLM 成本：預設關閉，僅做 feature gate。

---

## 結語
依據 dialogue_history_management_analysis.md 的原則與專案現況，我們已修復關鍵 Prompt/歷史/輸出格式問題，且規劃了從「降低工程複雜度 → 增強語境 → 提升一致性」的一條可落地路線。後續按 To‑Do 推進，可持續提升多輪穩定性與可維護性。

