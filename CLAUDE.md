# LLM Quest DSPy Project Memory

## 專案開發規範

### 測試結果和問題記錄規範
**每次重要修復和功能開發都必須完整記錄測試過程和結果**

#### 測試記錄必要內容
1. **問題描述**: 詳細記錄原始問題現象和影響範圍
2. **測試步驟**: 完整的測試執行命令和操作步驟
3. **預期vs實際結果**: 對比修復前後的具體測試結果
4. **異常情況記錄**: 所有錯誤、限制和邊界情況
5. **測試工具**: 將測試腳本加入版本控制，確保可重現性

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

## 專案依賴
- Docker
- Python (在容器內)
- DSPy 框架
- FastAPI（API 服務器）
- 其他依賴都已安裝在 Docker container 中