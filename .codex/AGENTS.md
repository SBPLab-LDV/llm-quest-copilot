# LLM Quest DSPy Project Memory

## 專案開發規範

### 核心開發哲學 - DSPy First & Prompt-Based 優先原則
**優先使用 DSPy 內建功能和 Gemini 的 prompt-based 能力，避免過度撰寫複雜自定義程式碼**

#### 開發優先級排序
1. **DSPy 內建模組優先**: 優先使用 DSPy 提供的現成 Signature、Module、Optimizer 等
2. **Prompt Engineering**: 透過精心設計的 prompt 讓 Gemini 自行完成複雜邏輯
3. **DSPy 組合模式**: 使用 DSPy 的 Chain、Parallel、Conditional 等組合現有模組
4. **最小化自定義程式碼**: 只有在 DSPy 無法直接支援時才撰寫自定義邏輯

#### 具體實施原則
- **優先查詢 DSPy 文檔**: 在實作新功能前，先確認 DSPy 是否已有相關模組
- **Prompt-first 思維**: 能用 prompt 描述解決的問題，就不要寫程式碼
- **組合勝過創造**: 優先組合現有 DSPy 元件，而非從零開始寫新功能
- **測試導向**: 透過測試驗證 DSPy 模組的效果，而非假設需要自定義實作

#### 範例對比
❌ **錯誤做法**: 自行實作複雜的對話狀態管理邏輯
✅ **正確做法**: 使用 DSPy Signature 定義狀態轉換，讓 Gemini 透過 prompt 處理

❌ **錯誤做法**: 手寫複雜的 JSON 解析和驗證程式碼
✅ **正確做法**: 使用 DSPy JSONAdapter 和精確的 output format prompt

❌ **錯誤做法**: 建立複雜的自定義 pipeline 管理系統
✅ **正確做法**: 使用 DSPy Chain 和 Module 組合現有功能

### 測試結果和問題記錄規範
**每次重要修復和功能開發都必須完整記錄測試過程和結果**

#### 測試記錄必要內容
1. **問題描述**: 詳細記錄原始問題現象和影響範圍
2. **測試步驟**: 完整的測試執行命令和操作步驟
3. **預期vs實際結果**: 對比修復前後的具體測試結果
4. **異常情況記錄**: 所有錯誤、限制和邊界情況
5. **測試工具**: 將測試腳本加入版本控制，確保可重現性
6. **Gemini Prompt 品質驗證**: 確認輸入 prompt 完整性、角色資訊清晰度和情境資訊充分性
7. **推理品質分析**: 檢查 reasoning 欄位是否包含實際邏輯推理，而非空泛或模板化內容
8. **模板回應檢測**: 識別並分析任何自我介紹、通用回應或混亂表達等模板化問題

#### 測試文件命名規範
- 主要測試結果記錄: `test_results_[功能名]_[修復類型].md`
- 診斷工具: `test_[功能名]_degradation.py`
- 驗證腳本: `test_[功能名]_[測試類型].py`

#### 必須記錄的測試類型
- **功能測試**: 核心功能是否正常工作
- **回歸測試**: 修復是否影響其他功能  
- **邊界測試**: 極端情況和錯誤處理
- **性能測試**: 修復對系統性能的影響
- **一致性測試**: 多次執行結果的穩定性

### Git Commit 規範 - 實驗驱動開發
**每個 commit 都必須是一個獨立可測試的實驗單元**

#### Commit Message 結構要求
每個 commit message 必須包含以下結構：

```
experiment: [實驗目標] - [具體功能描述]

Test Hypothesis: [實驗假設，必須是可測試和驗證的]

Implementation:
- [具體實現內容 1]
- [具體實現內容 2]
- [技術細節和架構變更]

Test Steps Executed:
1. docker exec dialogue-server-jiawei-dspy python /app/[測試腳本]
2. [具體執行的測試步驟 2]
3. [具體執行的測試步驟 3]
4. [驗證步驟]
5. [回歸測試或性能測試]

ACTUAL TEST RESULTS:
✅ SUCCESSES:
- [成功的測試結果 1]
- [量化的性能指標]
- [功能驗證結果]

❌ ERRORS ENCOUNTERED:
- [具體錯誤描述和錯誤代碼]
- [錯誤影響範圍分析]
- [失敗的測試案例]

ERROR DETAILS:
- Location: [錯誤發生的檔案和函數]
- Root Cause: [根本原因分析]
- Impact: [影響評估]
- Severity: [嚴重程度: LOW/MEDIUM/HIGH/CRITICAL]

DETAILED LOGS:
```
[關鍵的測試執行日誌片段]
[錯誤堆疊追踪]
[重要的除錯輸出]
```

Technical Details:
- Files: [修改的檔案清單與行數變更]
- Test Coverage: [測試覆蓋率和結果]
- Performance: [性能指標變化]
- Regression: [回歸測試結果]

Experiment Status: [✅ SUCCESSFUL / ⚠️ PARTIAL SUCCESS / ❌ FAILED]
- [狀態詳細說明]
- [後續所需修復項目]

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

#### 實驗驅動開發原則
1. **實驗假設先行**: 每個 commit 都要有明確可測試的假設
2. **測試步驟記錄**: 所有測試命令和操作步驟必須被詳實記錄
3. **結果量化記錄**: 成功和失敗都要有具體的數據和日誌
4. **錯誤詳實分析**: 包含錯誤類型、位置、影響範圍和解決方案
5. **可重現性**: 任何人都能根據記錄重現測試和驗證結果

#### 測試腳本要求
每個實驗性 commit 都應該包含：
- 專屬的測試腳本（如 `test_[功能名]_[日期].py`）
- Docker 容器內的測試執行命令
- 自動化的驗證和報告機制
- 錯誤處理和日誌記錄功能

## 重要執行環境要求

### Docker Container 執行
**所有 Python 程式碼必須透過 Docker container 執行**
- Container 名稱: `dialogue-server-jiawei-dspy`
- 執行方式: `docker exec dialogue-server-jiawei-dspy python /app/<script_name>.py`
- 工作目錄對應: 本地 `/home/sbplab/jiawei/llm-quest-dspy` 對應到容器內 `/app`

範例:
```bash
# 執行測試腳本
docker exec dialogue-server-jiawei-dspy python /app/test-config-debug.py

# 執行 API 服務器
docker exec dialogue-server-jiawei-dspy python /app/api_server.py

# 執行其他 Python 腳本
docker exec dialogue-server-jiawei-dspy python /app/<script_name>.py
```

## 專案架構

### 核心服務
- **API Server**: `api_server.py` - 主要的對話 API 服務器，運行在 port 8000
- **Dialogue Endpoint**: `http://localhost:8000/api/dialogue/text`
- **支援功能**: 角色配置、會話管理、語音識別選項

### 測試腳本
- `test-config-debug.py`: 測試 character_config 參數處理
- `api_debug.log`: API 除錯日誌
- `config_debug.log`: 配置除錯日誌

### 配置系統
- **配置文件**: `config/config.yaml`
- **角色配置支援**:
  - `name`: 角色名稱
  - `persona`: 角色個性
  - `backstory`: 背景故事
  - `goal`: 角色目標
  - `details`: 詳細設定（包含 fixed_settings 和 floating_settings）

### API 請求格式
```json
{
  "text": "使用者訊息",
  "character_id": "角色ID",
  "character_config": {
    "name": "角色名稱",
    "persona": "角色描述",
    "backstory": "背景故事",
    "goal": "目標",
    "details": {
      "fixed_settings": {},
      "floating_settings": {}
    }
  },
  "session_id": "會話ID（可選）"
}
```

### API 回應格式
```json
{
  "status": "success",
  "responses": ["回應選項1", "回應選項2", ...],
  "state": "NORMAL/CONFUSED",
  "dialogue_context": "對話情境",
  "session_id": "會話ID",
  "speech_recognition_options": null,
  "original_transcription": null
}
```

## 開發注意事項

1. **容器依賴**: 所有程式執行都需要 Docker container 環境，因為依賴項都安裝在容器內
2. **日誌系統**: 使用 Python logging 模組，同時輸出到 console 和檔案
3. **會話管理**: 支援會話持久性，使用 session_id 維持對話狀態
4. **角色系統**: 支援動態角色配置，可即時傳入 character_config
5. **語言**: 專案主要使用繁體中文介面和訊息

## Git 分支
- 當前分支: `feature/dspy-refactor`
- 主分支: `main`（通常用於 PR）


## 除錯和測試

### 實驗性測試腳本執行
```bash
# 統一對話模組測試
docker exec dialogue-server-jiawei-dspy python /app/test_unified_optimization.py

# 工廠模式 A/B 測試
docker exec dialogue-server-jiawei-dspy python /app/test_factory_optimization.py

# API 管理器調試
docker exec dialogue-server-jiawei-dspy python /app/debug_api_manager.py

# 完整回歸測試套件
docker exec dialogue-server-jiawei-dspy python /app/run_tests.py
```

### 測試配置處理
```bash
docker exec dialogue-server-jiawei-dspy python /app/test-config-debug.py
```

### 查看日誌
```bash
# API 日誌
tail -f api_debug.log

# 配置除錯日誌
tail -f config_debug.log

# UI 除錯日誌
tail -f ui_debug.log

# API 服務器日誌
tail -f api_server.log
```

## 常用命令

### 容器管理
```bash
# 查看容器狀態
docker ps | grep dialogue-server-jiawei-dspy

# 進入容器 shell
docker exec -it dialogue-server-jiawei-dspy bash

# 查看容器日誌
docker logs dialogue-server-jiawei-dspy
```

### 開發測試
```bash
# 執行 API 測試
docker exec dialogue-server-jiawei-dspy python /app/test-config-debug.py

# 檢查 API 健康狀態
curl http://localhost:8000/health

# 測試對話 API
curl -X POST http://localhost:8000/api/dialogue/text \
  -H "Content-Type: application/json" \
  -d '{"text": "您好", "character_id": "test"}'
```

## 專案依賴與 DSPy 使用指南

### 核心依賴
- Docker
- Python (在容器內)
- DSPy 框架
- FastAPI（API 服務器）
- 其他依賴都已安裝在 Docker container 中

### DSPy 框架使用重點

#### DSPy 核心概念
- **Signature**: 定義輸入輸出格式，讓 LM 理解任務結構
- **Module**: 封裝可重用的 LM 調用邏輯
- **Chain/Parallel**: 組合多個模組的執行流程
- **Optimizer**: 自動優化 prompt 和示例選擇

#### 建議的 DSPy 使用模式
1. **使用 Signature 定義清晰的任務介面**
   ```python
   class PatientResponseSignature(dspy.Signature):
       """根據醫師問題產生病患回應"""
       question = dspy.InputField()
       character_config = dspy.InputField()
       response = dspy.OutputField()
   ```

2. **優先使用內建 Adapter**
   - `JSONAdapter`: 結構化 JSON 輸出
   - `ChatAdapter`: 對話格式處理
   - `TextAdapter`: 純文字處理

3. **組合而非重寫**
   - 使用 `dspy.Chain` 串接多個步驟
   - 使用 `dspy.Parallel` 並行處理
   - 使用條件邏輯組合不同 Module

#### Prompt Engineering 最佳實踐
- **具體而詳細的指令**: 明確描述期望的行為和輸出格式
- **角色設定清晰**: 透過 prompt 建立清楚的角色定位
- **範例導向**: 在 prompt 中提供具體範例而非抽象描述
- **錯誤處理**: 在 prompt 中預先處理可能的邊界情況

#### 避免過度工程化
- **不要**為了程式碼整潔而犧牲 DSPy 的設計模式
- **不要**手寫可以用 DSPy Signature 定義的邏輯
- **不要**重新發明 DSPy 已經提供的功能
- **優先**信任 Gemini 的理解能力，透過清晰的 prompt 解決問題

## 🧠 Gemini 推理品質保證規範

### 核心原則
**每次測試都必須確保 Gemini 收到有意義的 prompt 並產生有意義的推理，避免返回模板化回應**

### Prompt 品質檢查
1. **輸入完整性**：確認所有角色資訊、對話歷史、情境資訊完整傳遞
2. **格式正確性**：檢查 DSPy Signature 和 JSON 格式要求明確
3. **指導清晰性**：驗證角色扮演和邏輯一致性指導有效

### 推理品質評估
1. **Reasoning 分析**：必須包含具體的情境分析和角色一致性檢查
2. **邏輯完整性**：推理過程應針對具體輸入，展現角色理解
3. **非模板化**：避免通用說明，要求具體的醫療情境分析

### 模板回應檢測
**識別並避免以下模板回應模式：**
- 自我介紹：「我是Patient_X」、「您好，我是」
- 通用回應：「您需要什麼幫助」、「能請您換個方式」
- 混亂表達：「沒有完全理解」、「需要更多資訊」
- 單一回應：應該有 5 個選項但只有 1 個

### 失敗分析框架
**當出現模板回應時，必須分析：**
- **技術問題**：Prompt 傳遞、DSPy 設定、JSON 解析
- **內容問題**：角色資訊充分性、情境清晰度、指導明確性
- **推理問題**：任務理解、角色扮演效果、邏輯檢查機制

### 品質驗證清單
```
每次測試必檢項目：
✅ Prompt 包含完整角色資訊
✅ Reasoning 欄位包含具體分析邏輯
✅ 回應符合角色設定且多樣化（5個不同回應）
✅ 無自我介紹或通用模板回應
✅ 狀態判斷有具體理由說明
✅ 對話情境分類準確具體
```