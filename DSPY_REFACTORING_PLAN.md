# DSPy 重構計畫文檔

> 最後更新：2025-01-11
> 
> 狀態：✅ Phase 1 已完成，進行中 Phase 2

## 目錄

1. [專案概述](#1-專案概述)
2. [現狀分析](#2-現狀分析)
3. [重構目標](#3-重構目標)
4. [技術架構設計](#4-技術架構設計)
5. [實施計畫與 To-do List](#5-實施計畫與-to-do-list)
6. [測試策略](#6-測試策略)
7. [風險管理](#7-風險管理)
8. [進度追蹤](#8-進度追蹤)
9. [附錄](#9-附錄)

---

## 1. 專案概述

### 1.1 背景
本專案是一個醫療對話系統，模擬病患與醫護人員的互動。目前使用傳統的提示工程方式，透過 YAML 模板和字串格式化來管理 prompts。

### 1.2 重構動機
- 提示詞管理分散且難以優化
- 缺乏結構化的輸入輸出驗證
- Few-shot examples 是硬編碼的，無法動態選擇
- 沒有自動評估和優化機制

### 1.3 DSPy 優勢
- **自動提示優化**：可自動優化 prompts 以提高品質
- **結構化管理**：使用 Signatures 定義清晰的輸入輸出
- **動態範例選擇**：根據情境自動選擇最相關的範例
- **評估框架**：內建評估和優化工具

---

## 2. 現狀分析

### 2.1 現有架構

```
llm-quest-dspy/
├── src/
│   ├── api/
│   │   └── server.py          # FastAPI 服務器
│   ├── core/
│   │   ├── character.py       # 角色數據模型
│   │   ├── dialogue.py        # 對話管理器（核心）
│   │   ├── prompt_manager.py  # 提示詞管理
│   │   └── state.py           # 狀態枚舉
│   ├── llm/
│   │   └── gemini_client.py   # Gemini API 客戶端
│   └── utils/
│       └── ...
├── prompts/
│   ├── templates/              # YAML 提示模板
│   ├── context_examples/       # 情境範例
│   └── context_keywords.yaml  # 情境關鍵字
└── run_tests.py               # 測試腳本（必須保持可用）
```

### 2.2 關鍵依賴
- **API 接口**：必須保持不變
  - POST `/api/dialogue/text`
  - POST `/api/dialogue/audio`
  - POST `/api/dialogue/select_response`
- **測試腳本**：`run_tests.py` 必須持續可用
- **Docker 環境**：所有代碼在 `dialogue-server-jiawei-dspy` 容器中執行

### 2.3 現有問題
1. PromptManager 使用字串格式化，難以追蹤和優化
2. 範例選擇是靜態的，基於預定義的情境
3. 沒有評估回應品質的標準化方法
4. 錯誤處理分散在各個模組中

---

## 3. 重構目標

### 3.1 核心目標
- ✅ **保持 API 完全兼容**：不改變任何 API 接口
- ✅ **漸進式遷移**：可隨時切換新舊版本
- ✅ **持續可測試**：每個階段都能運行 `run_tests.py`
- ✅ **提升品質**：透過 DSPy 優化提升回應品質

### 3.2 技術目標
- 使用 DSPy Signatures 定義清晰的輸入輸出
- 實現動態 few-shot example 選擇
- 建立自動評估和優化流程
- 改善錯誤處理和恢復機制

### 3.3 非目標
- ❌ 不改變 API 接口
- ❌ 不改變數據庫結構（如果有）
- ❌ 不改變前端代碼

---

## 4. 技術架構設計

### 4.1 整體架構

```
┌─────────────────────────────────────┐
│           API Layer (不變)           │
│         src/api/server.py           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│       Factory Layer (新增)           │
│    src/core/dialogue_factory.py     │
│         (根據配置切換)                │
└──────┬────────────────┬─────────────┘
       │                │
       ▼                ▼
┌──────────────┐ ┌────────────────────┐
│  原有實現     │ │   DSPy 實現        │
│ DialogueManager│ │DialogueManagerDSPy │
└──────────────┘ └────────────────────┘
```

### 4.2 DSPy 模組設計

#### 4.2.1 Signatures
```python
# src/core/dspy/signatures.py

class PatientResponseSignature(dspy.Signature):
    """生成病患回應"""
    user_input: str = dspy.InputField()
    character_info: dict = dspy.InputField()
    conversation_history: list = dspy.InputField()
    
    responses: list = dspy.OutputField(desc="5個回應選項")
    state: str = dspy.OutputField()
    dialogue_context: str = dspy.OutputField()

class ContextClassificationSignature(dspy.Signature):
    """判斷對話情境"""
    user_input: str = dspy.InputField()
    keywords: dict = dspy.InputField()
    
    context: str = dspy.OutputField()
```

#### 4.2.2 模組結構
```python
# src/core/dspy/dialogue_module.py

class DSPyDialogueModule(dspy.Module):
    def __init__(self):
        self.context_classifier = dspy.ChainOfThought(ContextClassificationSignature)
        self.response_generator = dspy.ChainOfThought(PatientResponseSignature)
        self.example_bank = ExampleBank()
```

### 4.3 配置管理

```yaml
# config/config.yaml
dspy:
  enabled: false          # 初始關閉，逐步開啟
  optimize: false         # 是否使用優化後的 prompts
  model: "gemini-2.0-flash-exp"
  temperature: 0.9
  ab_testing:
    enabled: false
    percentage: 50        # DSPy 版本的流量百分比
```

---

## 5. 實施計畫與 To-do List

### Phase 0: 準備工作（Day 1-2）
> 目標：設置環境，不影響現有系統

#### To-do List:
- [ ] **0.1 環境設置**
  - [ ] 在 Docker container 中安裝 DSPy: `docker exec dialogue-server-jiawei-dspy pip install dspy-ai`
  - [ ] 驗證 DSPy 安裝成功
  - [ ] 創建 `src/core/dspy/` 目錄結構
  
- [ ] **0.2 基礎配置**
  - [ ] 更新 `config/config.yaml` 添加 DSPy 配置項
  - [ ] 創建 `src/core/dspy/__init__.py`
  - [ ] 創建 `src/core/dspy/config.py` - DSPy 配置管理
  
- [ ] **0.3 測試準備**
  - [ ] 備份現有測試結果作為基準
  - [ ] 創建 `tests/dspy/` 目錄
  - [ ] 準備測試數據集

**測試點**：運行 `run_tests.py` 確保現有系統正常

---

### Phase 1: DSPy 基礎設施（Day 3-5）
> 目標：建立 DSPy 與 Gemini 的連接，可獨立測試

#### To-do List:
- [ ] **1.1 Gemini 適配器**
  - [ ] 創建 `src/llm/dspy_gemini_adapter.py`
  - [ ] 實現 `DSPyGeminiLM` 類，繼承 `dspy.LM`
  - [ ] 實現 `__call__` 方法包裝 Gemini API
  - [ ] 添加錯誤處理和重試邏輯
  - [ ] 編寫單元測試 `tests/dspy/test_gemini_adapter.py`

- [ ] **1.2 DSPy 初始化**
  - [ ] 創建 `src/core/dspy/setup.py`
  - [ ] 實現 DSPy 初始化函數
  - [ ] 配置 DSPy 全局設置
  - [ ] 測試與 Gemini 的連接

- [ ] **1.3 基礎 Signatures**
  - [ ] 創建 `src/core/dspy/signatures.py`
  - [ ] 實現 `PatientResponseSignature`
  - [ ] 實現 `ContextClassificationSignature`
  - [ ] 實現 `ResponseEvaluationSignature`
  - [ ] 編寫 signature 測試

**測試點**：
- 運行 `docker exec dialogue-server-jiawei-dspy python -m tests.dspy.test_gemini_adapter`
- 確認 DSPy 可以成功調用 Gemini API
- 運行 `run_tests.py` 確保不影響現有系統

---

### Phase 2: 範例管理系統（Day 6-8）
> 目標：將 YAML 範例轉換為 DSPy Examples

#### To-do List:
- [ ] **2.1 範例加載器**
  - [ ] 創建 `src/core/dspy/example_loader.py`
  - [ ] 實現 YAML 到 `dspy.Example` 的轉換
  - [ ] 處理所有 context_examples 文件
  - [ ] 實現範例驗證機制

- [ ] **2.2 範例銀行**
  - [ ] 創建 `src/core/dspy/example_bank.py`
  - [ ] 實現 `ExampleBank` 類
  - [ ] 實現範例索引和搜索
  - [ ] 實現相似度計算
  - [ ] 實現 `get_relevant_examples(context, k=5)` 方法

- [ ] **2.3 範例選擇器**
  - [ ] 創建 `src/core/dspy/example_selector.py`
  - [ ] 實現基於情境的範例選擇
  - [ ] 實現基於相似度的範例選擇
  - [ ] 添加範例多樣性保證

**測試點**：
- 測試範例加載是否正確
- 驗證範例選擇邏輯
- 運行 `run_tests.py` 確保系統正常

---

### Phase 3: DSPy 對話模組（Day 9-12）
> 目標：實現核心 DSPy 對話模組

#### To-do List:
- [ ] **3.1 核心模組**
  - [ ] 創建 `src/core/dspy/dialogue_module.py`
  - [ ] 實現 `DSPyDialogueModule` 類
  - [ ] 整合 context classifier
  - [ ] 整合 response generator
  - [ ] 實現 forward 方法

- [ ] **3.2 提示優化器**
  - [ ] 創建 `src/core/dspy/optimizer.py`
  - [ ] 實現訓練數據準備
  - [ ] 實現 `BootstrapFewShot` 優化
  - [ ] 實現優化結果保存和加載

- [ ] **3.3 評估器**
  - [ ] 創建 `src/core/dspy/evaluator.py`
  - [ ] 實現回應品質評估
  - [ ] 實現情境準確度評估
  - [ ] 實現對話連貫性評估

**測試點**：
- 獨立測試 DSPyDialogueModule
- 比較 DSPy 輸出與原始輸出
- 運行 `run_tests.py` 確保兼容性

---

### Phase 4: 適配層實現（Day 13-15）
> 目標：創建與現有系統的橋接層

#### To-do List:
- [ ] **4.1 對話管理器適配**
  - [ ] 創建 `src/core/dspy/dialogue_manager_dspy.py`
  - [ ] 實現 `DialogueManagerDSPy` 類
  - [ ] 繼承原有 `DialogueManager` 接口
  - [ ] 實現 `process_turn` 方法
  - [ ] 保持日誌和錯誤處理邏輯

- [ ] **4.2 工廠模式**
  - [ ] 創建 `src/core/dialogue_factory.py`
  - [ ] 實現 `create_dialogue_manager` 工廠函數
  - [ ] 根據配置返回對應實現
  - [ ] 添加版本切換日誌

- [ ] **4.3 配置管理**
  - [ ] 更新配置加載邏輯
  - [ ] 實現運行時配置切換
  - [ ] 添加配置驗證

**測試點**：
- 測試工廠模式切換
- 使用 DSPy 版本運行 `run_tests.py`
- 比較新舊版本輸出差異

---

### Phase 5: 整合與切換（Day 16-18）
> 目標：整合到 API 服務器，實現無縫切換

#### To-do List:
- [ ] **5.1 API 整合**
  - [ ] 修改 `src/api/server.py` 導入工廠函數
  - [ ] 更新會話創建邏輯
  - [ ] 添加版本標記到回應頭
  - [ ] 實現 A/B 測試邏輯

- [ ] **5.2 監控和日誌**
  - [ ] 添加性能監控
  - [ ] 記錄版本使用統計
  - [ ] 實現錯誤率追蹤
  - [ ] 創建對比報告

- [ ] **5.3 回退機制**
  - [ ] 實現快速回退開關
  - [ ] 添加健康檢查
  - [ ] 實現自動回退條件

**測試點**：
- 完整運行 `run_tests.py`
- 進行負載測試
- 測試回退機制

---

### Phase 6: 優化與完善（Day 19-21）
> 目標：優化性能，完善功能

#### To-do List:
- [ ] **6.1 性能優化**
  - [ ] 實現響應緩存
  - [ ] 優化範例選擇算法
  - [ ] 減少 API 調用次數
  - [ ] 實現批處理

- [ ] **6.2 品質提升**
  - [ ] 收集真實對話數據
  - [ ] 運行 DSPy 優化器
  - [ ] 調整參數
  - [ ] A/B 測試結果分析

- [ ] **6.3 文檔更新**
  - [ ] 更新 CLAUDE.md
  - [ ] 更新 API 文檔
  - [ ] 編寫遷移指南
  - [ ] 創建故障排除指南

**測試點**：
- 性能基準測試
- 品質評估報告
- 最終驗收測試

---

## 6. 測試策略

### 6.1 測試原則
1. **持續測試**：每個 Phase 完成後立即測試
2. **向後兼容**：確保 `run_tests.py` 始終可用
3. **漸進驗證**：從單元測試到整合測試
4. **對比測試**：新舊版本輸出對比

### 6.2 測試層級

#### Level 1: 單元測試
```bash
# 測試單個 DSPy 組件
docker exec dialogue-server-jiawei-dspy python -m pytest tests/dspy/
```

#### Level 2: 模組測試
```bash
# 測試 DSPy 模組整合
docker exec dialogue-server-jiawei-dspy python tests/test_dspy_module.py
```

#### Level 3: API 測試
```bash
# 運行標準測試腳本
docker exec dialogue-server-jiawei-dspy python /app/run_tests.py
```

#### Level 4: 對比測試
```bash
# 運行新舊版本對比
docker exec dialogue-server-jiawei-dspy python tests/compare_versions.py
```

### 6.3 測試檢查點

| Phase | 測試項目 | 預期結果 | 通過標準 |
|-------|---------|---------|---------|
| 0 | 環境設置 | DSPy 安裝成功 | import dspy 無錯誤 |
| 1 | Gemini 適配器 | DSPy 可調用 Gemini | 獲得有效回應 |
| 2 | 範例管理 | 範例正確加載 | 所有 YAML 轉換成功 |
| 3 | DSPy 模組 | 模組獨立運行 | 輸出格式正確 |
| 4 | 適配層 | 接口兼容 | run_tests.py 通過 |
| 5 | API 整合 | 完整功能 | 所有 API 端點正常 |
| 6 | 優化完成 | 品質提升 | 評估指標改善 |

---

## 7. 風險管理

### 7.1 技術風險

| 風險 | 影響 | 可能性 | 緩解措施 |
|-----|-----|-------|---------|
| DSPy 與 Gemini 不兼容 | 高 | 中 | 建立適配器層，保留原始客戶端 |
| 回應品質下降 | 高 | 低 | A/B 測試，保留切換機制 |
| 性能降低 | 中 | 中 | 實現緩存，優化調用 |
| 範例轉換錯誤 | 低 | 低 | 驗證機制，保留原始數據 |

### 7.2 專案風險

| 風險 | 影響 | 可能性 | 緩解措施 |
|-----|-----|-------|---------|
| 時程延誤 | 中 | 中 | 階段性交付，核心功能優先 |
| 測試不足 | 高 | 低 | 自動化測試，持續整合 |
| 文檔不完整 | 低 | 中 | 邊做邊記錄，定期更新 |

### 7.3 回退計畫

1. **快速回退**：配置開關，5分鐘內回退
2. **部分回退**：只回退有問題的模組
3. **數據保留**：所有優化結果保存，可重用

---

## 8. 進度追蹤

### 8.1 里程碑

| 里程碑 | 目標日期 | 狀態 | 備註 |
|-------|---------|-----|------|
| M1: 環境準備完成 | Day 2 | 🔄 進行中 | |
| M2: DSPy 基礎設施 | Day 5 | ⏳ 待開始 | |
| M3: 範例系統完成 | Day 8 | ⏳ 待開始 | |
| M4: 核心模組完成 | Day 12 | ⏳ 待開始 | |
| M5: 適配層完成 | Day 15 | ⏳ 待開始 | |
| M6: API 整合完成 | Day 18 | ⏳ 待開始 | |
| M7: 優化完成 | Day 21 | ⏳ 待開始 | |

### 8.2 進度統計

```
總任務數: 54
已完成: 15 (28%)
進行中: 3 (5%)
待開始: 36 (67%)

Phase 完成度:
Phase 0: [██████████] 100% ✅ 已完成
Phase 1: [██████████] 100% ✅ 已完成
Phase 2: [█─────────] 10% 🔄 進行中
Phase 3: [----------] 0%
Phase 4: [----------] 0%
Phase 5: [----------] 0%
Phase 6: [----------] 0%
```

### 8.3 決策記錄

| 日期 | 決策 | 理由 | 影響 |
|-----|-----|-----|-----|
| 2025-01-11 | 使用工廠模式 | 便於切換實現 | 需要修改 server.py |
| 2025-01-11 | 保留原始 DialogueManager | 降低風險 | 代碼量增加 |
| 2025-01-11 | Phase 0 & 1 完成 | DSPy 基礎設施建立完成 | 可以開始 Phase 2 |
| 2025-01-11 | 使用 DSPy 3.0.3 語法 | 修正 Signature 定義錯誤 | Signatures 現在正常工作 |
| 2025-01-11 | 創建進度報告 | 記錄實施過程和教訓 | 便於後續階段參考 |

---

## 9. 附錄

### 9.1 代碼範例

#### A. DSPy Signature 範例
```python
class PatientResponseSignature(dspy.Signature):
    """生成病患回應的簽名"""
    
    # 輸入欄位
    user_input: str = dspy.InputField(
        desc="護理人員的輸入或問題"
    )
    character_name: str = dspy.InputField(
        desc="病患角色名稱"
    )
    character_persona: str = dspy.InputField(
        desc="病患的個性描述"
    )
    character_backstory: str = dspy.InputField(
        desc="病患的背景故事"
    )
    character_details: dict = dspy.InputField(
        desc="病患的詳細設定，包含固定和浮動設定"
    )
    conversation_history: list = dspy.InputField(
        desc="最近的對話歷史"
    )
    
    # 輸出欄位
    responses: list = dspy.OutputField(
        desc="5個不同的回應選項"
    )
    state: str = dspy.OutputField(
        desc="對話狀態：NORMAL, CONFUSED, TRANSITIONING, 或 TERMINATED"
    )
    dialogue_context: str = dspy.OutputField(
        desc="當前對話情境，如：醫師查房、病房日常等"
    )
```

#### B. 工廠函數範例
```python
def create_dialogue_manager(character: Character, 
                           use_terminal: bool = False, 
                           log_dir: str = "logs") -> DialogueManager:
    """根據配置創建對話管理器
    
    Args:
        character: 角色實例
        use_terminal: 是否使用終端模式
        log_dir: 日誌目錄
        
    Returns:
        DialogueManager 或 DialogueManagerDSPy 實例
    """
    config = load_config()
    
    # 檢查是否啟用 DSPy
    if config.get('dspy', {}).get('enabled', False):
        logger.info("使用 DSPy 版本的 DialogueManager")
        from .dspy.dialogue_manager_dspy import DialogueManagerDSPy
        return DialogueManagerDSPy(character, use_terminal, log_dir)
    else:
        logger.info("使用原始版本的 DialogueManager")
        from .dialogue import DialogueManager
        return DialogueManager(character, use_terminal, log_dir)
```

#### C. 測試腳本範例
```python
# tests/test_dspy_compatibility.py
import sys
sys.path.append('/app')

def test_api_compatibility():
    """測試 API 兼容性"""
    from run_tests import text_dialogue
    
    # 測試文本對話
    response = text_dialogue(
        text="您好，今天感覺如何？",
        character_id="1"
    )
    
    # 驗證響應格式
    assert "status" in response
    assert "responses" in response
    assert "state" in response
    assert "dialogue_context" in response
    assert "session_id" in response
    
    # 驗證響應內容
    assert len(response["responses"]) == 5
    assert response["state"] in ["NORMAL", "CONFUSED", "TRANSITIONING", "TERMINATED"]
    
    print("✅ API 兼容性測試通過")

if __name__ == "__main__":
    test_api_compatibility()
```

### 9.2 常用命令

```bash
# 安裝 DSPy
docker exec dialogue-server-jiawei-dspy pip install dspy-ai

# 運行測試
docker exec dialogue-server-jiawei-dspy python /app/run_tests.py

# 查看日誌
docker exec dialogue-server-jiawei-dspy tail -f /app/api_server.log

# 切換到 DSPy 版本
docker exec dialogue-server-jiawei-dspy python -c "
import yaml
with open('/app/config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)
config['dspy'] = {'enabled': True}
with open('/app/config/config.yaml', 'w') as f:
    yaml.dump(config, f)
"

# 運行性能測試
docker exec dialogue-server-jiawei-dspy python /app/tests/performance_test.py
```

### 9.3 參考資源

- [DSPy 官方文檔](https://github.com/stanfordnlp/dspy)
- [DSPy 範例](https://github.com/stanfordnlp/dspy/tree/main/examples)
- [Gemini API 文檔](https://ai.google.dev/docs)
- 專案原始文檔：`doc/`

---

## 更新日誌

| 日期 | 版本 | 更新內容 |
|-----|------|---------|
| 2025-01-11 | v1.0 | 初始版本，完整重構計畫 |

---

## 聯絡資訊

如有問題或建議，請：
1. 更新此文檔的相關章節
2. 在決策記錄中添加新項目
3. 更新進度追蹤

---

**文檔狀態圖例**：
- ✅ 已完成
- 🔄 進行中
- ⏳ 待開始
- ❌ 已取消
- 🚧 規劃中