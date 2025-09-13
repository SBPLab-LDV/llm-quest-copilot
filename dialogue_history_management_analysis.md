# 對話歷史管理與多輪一致性架構分析報告

## 概述

本報告詳細分析了 LLM Quest DSPy 專案中的對話歷史管理機制、多輪對話一致性維護架構，以及與 DSPy 框架的整合情況。

## 1. 整體架構圖

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            對話歷史管理與一致性架構                              │
└─────────────────────────────────────────────────────────────────────────────┘

                            ┌─────────────────┐
                            │   API Server    │
                            │  (FastAPI)      │
                            │  Session Store  │
                            └─────────┬───────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
            ┌───────▼────────┐                 ┌───────▼────────┐
            │ Dialogue       │                 │ Character      │
            │ Factory        │                 │ Management     │
            │ (三種實現)      │                 │ & Config       │
            └───────┬────────┘                 └────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
┌───────▼─┐  ┌─────▼─────┐  ┌──▼─────────────┐
│Original │  │DSPy Basic │  │DSPy Optimized  │
│Manager  │  │Manager    │  │(Unified)       │
└─────────┘  └───────────┘  └─────┬──────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   UnifiedDSPyModule      │
                    │   (Single API Call)      │
                    └─────────────┬─────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    │                             │                             │
┌───▼─────────────┐     ┌────────▼──────────┐     ┌─────────▼─────────┐
│History Enhanced │     │Consistency Check  │     │State & Context    │
│Management       │     │(Rule-based)       │     │Classification     │
│- 8 turns max    │     │- Medical facts    │     │- JSON Signature   │
│- Context aware  │     │- Timeline track   │     │- Prompt-based     │
│- Character      │     │- Self-intro       │     │- Multi-field      │
│  consistency    │     │  detection        │     │  output           │
└─────────────────┘     └───────────────────┘     └───────────────────┘
```

## 2. 對話歷史管理機制

### 2.1 會話層級管理 (API Server)

**文件位置**: `src/api/server.py`

**核心機制**:
- **會話存儲**: `session_store` 字典維護多客戶端狀態
- **會話數據結構**:
  ```python
  session_store[session_id] = {
      "dialogue_manager": dialogue_manager,
      "character_id": character_id,
      "implementation_version": implementation_version,
      "created_at": timestamp,
      "last_activity": timestamp
  }
  ```
- **生命週期管理**: 1小時無活動自動清理 (`cleanup_old_sessions`)
- **狀態持久化**: 每次請求更新 `last_activity`

### 2.2 智能歷史選擇策略

**文件位置**: `src/core/dspy/unified_dialogue_module.py:327-370`

**核心實現**:
```python
def _get_enhanced_conversation_history(self, conversation_history, character_name, character_persona):
    max_history = 8  # 最多保留8輪對話

    if len(conversation_history) > max_history:
        # 策略：保留前3輪（角色建立期）+ 最近5輪（當前對話）
        important_start = conversation_history[:6]  # 前3輪對話
        recent = conversation_history[-(max_history-3):]  # 最近5輪
        combined = important_start + recent

    # 添加角色一致性與邏輯一致性檢查提醒
    character_reminder = f"""
    [重要: 您是 {character_name}，{character_persona}。保持角色一致性。
    【邏輯一致性檢查】請仔細檢查上述對話歷史中的醫療事實（症狀、發燒狀況、
    疼痛程度、服藥情況等），確保您的回應與之前提到的所有事實保持完全一致]
    """
```

**設計特點**:
- **混合窗口策略**: 角色建立期 + 最近對話
- **去重機制**: 避免重複歷史記錄
- **上下文增強**: 自動添加角色一致性提醒
- **醫療邏輯檢查**: 內置醫療事實一致性提示

### 2.3 對話歷史格式化

**實現位置**: 各個對話管理器的 `conversation_history` 屬性

**格式規範**:
- `"護理人員: {user_input}"` - 護理人員輸入
- `"{character_name}: {response}"` - 病患回應
- `"[系統]: {system_message}"` - 系統訊息

## 3. DSPy 框架整合分析

### 3.1 三種對話管理器實現比較

| 特徵 | Original Manager | DSPy Basic Manager | DSPy Optimized Manager |
|------|------------------|-------------------|----------------------|
| **檔案位置** | `src/core/dialogue.py` | `src/core/dspy/dialogue_manager_dspy.py` | `src/core/dspy/optimized_dialogue_manager.py` |
| **API 調用次數** | N/A | 3次/對話 | 1次/對話 |
| **對話歷史管理** | 基本 | 基本 | 增強(8輪智能選擇) |
| **一致性檢查** | 無 | 無 | 規則式檢查器 |
| **DSPy 整合度** | N/A | 中等 | 高 |
| **性能監控** | 無 | 基本統計 | 完整監控 |
| **角色一致性** | 基本 | 基本 | 增強提醒 |
| **API 效率** | N/A | 基準 | 66.7% 節省 |

### 3.2 DSPy Signature 設計

**核心 Signature**: `UnifiedPatientResponseSignature`
**檔案位置**: `src/core/dspy/unified_dialogue_module.py:21-74`

**設計特點**:
```python
class UnifiedPatientResponseSignature(dspy.Signature):
    """統一的病患回應生成簽名 - JSON 輸出版本

    將情境分類、回應生成、狀態判斷合併為單一調用，
    減少 API 使用次數從 3 次降至 1 次。
    """

    # 輸入欄位
    user_input = dspy.InputField(desc="護理人員的輸入或問題")
    character_name = dspy.InputField(desc="病患角色的名稱")
    character_persona = dspy.InputField(desc="病患的個性描述")
    character_backstory = dspy.InputField(desc="病患的背景故事")
    character_goal = dspy.InputField(desc="病患的目標")
    character_details = dspy.InputField(desc="病患的詳細設定")
    conversation_history = dspy.InputField(desc="最近的對話歷史")
    available_contexts = dspy.InputField(desc="可用的對話情境列表")

    # 輸出欄位 - 統一的回應結果
    reasoning = dspy.OutputField(desc="推理過程：包含情境分析、角色一致性檢查...")
    character_consistency_check = dspy.OutputField(desc="角色一致性檢查：確認回應符合已建立的角色人格")
    context_classification = dspy.OutputField(desc="對話情境分類")
    confidence = dspy.OutputField(desc="情境分類的信心度")
    responses = dspy.OutputField(desc="5個不同的病患回應選項")
    state = dspy.OutputField(desc="對話狀態：NORMAL、CONFUSED、TRANSITIONING 或 TERMINATED")
    dialogue_context = dspy.OutputField(desc="當前對話情境描述")
    state_reasoning = dspy.OutputField(desc="狀態判斷的理由說明")
```

### 3.3 DSPy 使用模式評估

#### ✅ 良好的 DSPy 整合部分

1. **Signature 設計合理**:
   - 清晰的輸入輸出定義
   - 詳細的字段描述
   - 符合醫療對話需求

2. **ChainOfThought 使用**:
   ```python
   self.unified_response_generator = dspy.ChainOfThought(UnifiedPatientResponseSignature)
   ```

3. **JSONAdapter 默認使用**: 利用 DSPy 內建的結構化輸出處理

4. **統一模組設計**: 將多步驟合併為單一調用，符合 DSPy 組合理念

#### ⚠️ 可改進的 DSPy 使用部分

1. **過度自定義分解** (`dialogue_module.py`):
   ```python
   # 當前實現：過度分解為多個步驟
   context_prediction = self._classify_context(...)
   relevant_examples = self._select_examples(...)
   response_prediction = self._generate_response(...)
   state_prediction = self._determine_state_transition(...)
   ```

2. **範例機制利用不足**:
   - `ExampleSelector` 存在但未充分利用 DSPy 的 few-shot 能力
   - 缺乏動態範例選擇和學習機制

3. **複雜錯誤處理**:
   - 過多的手動回退邏輯
   - 應該更信任 DSPy 和 Gemini 的能力

## 4. 多輪對話一致性機制

### 4.1 規則式一致性檢查器

**檔案位置**: `src/core/dspy/consistency_checker.py`

**核心組件**:

#### 4.1.1 醫療事實追蹤器 (`MedicalFactTracker`)
```python
class MedicalFactTracker:
    # 發燒狀態檢測
    fever_neg_patterns = [r"沒有發燒", r"沒發燒", r"不發燒"]
    fever_pos_patterns = [r"發燒", r"發熱", r"體溫(有)?升高"]

    # 疼痛狀態檢測
    pain_neg_patterns = [r"不痛", r"沒有痛", r"沒痛"]
    pain_pos_patterns = [r"痛", r"疼", r"酸痛", r"不舒服"]

    # 時間標記識別
    time_tokens = {
        r"現在|目前|剛剛|剛才": 1.0,
        r"(今天|今早|今天早上)": 0.9,
        r"(幾|數)小時前": 0.8,
        r"(昨天|昨晚)": 0.6,
        r"前天": 0.5,
        r"(上週|上周)": 0.2,
    }
```

#### 4.1.2 矛盾檢測器 (`ContradictionDetector`)
```python
def detect(self, previous_facts, new_facts):
    contradictions = []

    # 發燒狀態翻轉檢測
    if previous_facts.get("fever") != new_facts.get("fever"):
        contradictions.append(Contradiction(
            type="fever_state_flip",
            severity="high",
            description="發燒狀態前後不一致"
        ))

    # 疼痛狀態翻轉檢測
    if previous_facts.get("pain") != new_facts.get("pain"):
        contradictions.append(Contradiction(
            type="pain_state_flip",
            severity="medium",
            description="疼痛狀態前後不一致"
        ))
```

#### 4.1.3 內容品質檢測
```python
self_intro_patterns = [r"我是Patient", r"我是[\u4e00-\u9fa5A-Za-z0-9_]+", r"您好，我是"]
generic_patterns = [r"我可能沒有完全理解", r"能請您換個方式說明", r"您需要什麼幫助"]
```

### 4.2 一致性評分機制

**評分公式**:
```python
penalties = (
    0.25 * len(timeline_issues) +      # 時間線問題
    0.25 * len(fever_issues) +         # 發燒狀態矛盾
    0.15 * len(pain_issues) +          # 疼痛狀態矛盾
    0.25 * len(self_intro_issues) +    # 自我介紹問題
    0.10 * len(generic_issues)         # 通用回應問題
)
score = max(0.0, 1.0 - min(1.0, penalties))
```

**嚴重度分級**:
- `high`: 自我介紹問題 或 發燒狀態矛盾
- `medium`: 時間線矛盾 或 疼痛狀態矛盾 或 通用回應
- `low`: 其他情況

### 4.3 自動修正機制

**檔案位置**: `unified_dialogue_module.py:428-462`

```python
def _apply_consistency_fixes(self, responses, consistency_result):
    if consistency_result.severity == 'high':
        # 移除自我介紹/明顯矛盾回應
        fixed = [r for r in fixed if all(k not in str(r) for k in ["我是Patient", "您好，我是"])]

        # 若全被清空，提供安全的中性回應
        if not fixed:
            fixed = [
                "還可以，傷口有點緊繃。",
                "目前狀況還算穩定。",
                "偶爾會覺得有點不舒服。"
            ]
    else:
        # medium/low：加提示尾註
        hint = "（保持與先前陳述一致）"
        fixed = [f"{r}{hint}" for r in fixed]
```

## 5. 工廠模式與多實現管理

### 5.1 對話管理器工廠

**檔案位置**: `src/core/dialogue_factory.py`

**核心功能**:
```python
def create_dialogue_manager(character, use_terminal=False, log_dir="logs", force_implementation=None):
    """根據配置創建對話管理器"""

    # 自動選擇實現
    config = DSPyConfig()
    if config.is_dspy_enabled():
        if config.is_unified_module_enabled():
            return _create_optimized_dspy_manager(...)  # 優化版
        else:
            return _create_dspy_manager(...)  # 基本版
    else:
        return _create_original_manager(...)  # 原始版
```

### 5.2 實現版本檢測

**API Server 中的版本管理**:
```python
def create_dialogue_manager_with_monitoring(character, log_dir="logs/api"):
    manager = create_dialogue_manager(character, use_terminal=False, log_dir=log_dir)

    # 檢測實現版本
    implementation_version = "original"
    if hasattr(manager, 'optimization_enabled') and manager.optimization_enabled:
        implementation_version = "optimized"
    elif hasattr(manager, 'dspy_enabled') and manager.dspy_enabled:
        implementation_version = "dspy"

    return manager, implementation_version
```

## 6. 性能監控與統計

### 6.1 統一模組性能統計

**檔案位置**: `unified_dialogue_module.py:401-426`

```python
def get_unified_statistics(self):
    return {
        'api_calls_saved': self.unified_stats['api_calls_saved'],
        'total_unified_calls': self.unified_stats['total_unified_calls'],
        'success_rate': self.unified_stats['success_rate'],
        'api_efficiency': {
            'calls_per_conversation': 1,  # 統一模式：每次對話僅1次調用
            'original_calls_per_conversation': 3,  # 原始模式：每次對話3次調用
            'efficiency_improvement': '66.7%',
            'total_calls_saved': self.unified_stats['api_calls_saved']
        }
    }
```

### 6.2 API Server 性能監控

**檔案位置**: `src/api/server.py:658-729`

**監控端點**:
- `/api/monitor/stats` - 性能統計數據
- `/api/monitor/comparison` - DSPy vs 原始實現對比
- `/api/monitor/errors` - 錯誤摘要
- `/api/health/status` - 系統健康狀況

## 7. DSPy 最佳實踐評估

### 7.1 符合 DSPy 原則的部分

✅ **Prompt-first 思維**:
- 統一模組通過精確的 prompt 描述讓 Gemini 處理複雜邏輯
- 避免過度程式化的邏輯處理

✅ **組合勝過創造**:
- 使用 DSPy 的內建 JSONAdapter
- 利用 ChainOfThought 模組

✅ **單一責任**:
- UnifiedPatientResponseSignature 承擔統一的對話生成責任

### 7.2 違反 DSPy 原則的部分

❌ **過度工程化**:
- `dialogue_module.py` 中的多步驟分解 (情境分類→範例選擇→回應生成→狀態轉換)
- 應該更信任 DSPy 和 Gemini 的整合能力

❌ **範例利用不足**:
- ExampleSelector 存在但未充分利用 DSPy 的 few-shot 能力
- 缺乏動態學習和適應機制

❌ **複雜錯誤處理**:
- 過多的手動回退邏輯
- 應該通過更好的 prompt 設計解決問題

## 8. 改進建議

### 8.1 短期改進 (符合 DSPy First 原則)

1. **簡化 DSPy 實現**:
   - 將 `dialogue_module.py` 的多步驟調用統一為 UnifiedModule 模式
   - 移除過度分解的處理流程

2. **增強範例機制**:
   - 充分利用 DSPy 的 few-shot 能力
   - 實現動態範例選擇和學習

3. **簡化錯誤處理**:
   - 減少複雜的回退邏輯
   - 通過更精確的 prompt 設計提升穩定性

### 8.2 中期優化

1. **語意關聯歷史管理**:
   - 在歷史選擇中加入語意重要性權重
   - 實現動態窗口大小調整

2. **擴展一致性檢查**:
   - 添加更多醫療領域的事實類型
   - 結合簡單的語意向量比較

3. **統一最佳實踐**:
   - 將 Optimized 版本設為默認實現
   - 標準化所有實現的接口

### 8.3 長期發展

1. **學習型一致性**:
   - 基於歷史對話學習個性化一致性模式
   - 自動發現新的醫療事實關聯

2. **智能歷史管理**:
   - 基於對話內容重要性的動態選擇
   - 跨會話的知識累積

3. **DSPy 深度整合**:
   - 利用 DSPy 的優化器自動改進 prompt
   - 實現端到端的 DSPy pipeline

## 9. 結論

該專案在對話歷史管理和多輪一致性方面具有以下特點：

**優勢**:
- 三層實現架構提供了靈活性和漸進式優化路徑
- 統一模組實現了顯著的 API 效率提升 (66.7%)
- 規則式一致性檢查避免了額外的 LLM 調用
- 智能歷史選擇策略平衡了上下文完整性和效率

**改進空間**:
- DSPy 整合可以更深入，減少自定義邏輯
- 範例機制和 few-shot 能力利用不足
- 錯誤處理邏輯過於複雜，應更信任 DSPy 能力

**總體評估**:
該架構在實用性和效率方面表現良好，特別是 DSPy Optimized 版本展現了良好的工程實踐。通過進一步簡化和深化 DSPy 整合，可以實現更好的可維護性和擴展性。

---

**分析完成時間**: 2025-09-13
**分析覆蓋文件**:
- `src/api/server.py`
- `src/core/dspy/unified_dialogue_module.py`
- `src/core/dspy/dialogue_manager_dspy.py`
- `src/core/dspy/dialogue_module.py`
- `src/core/dspy/consistency_checker.py`
- `src/core/dialogue_factory.py`