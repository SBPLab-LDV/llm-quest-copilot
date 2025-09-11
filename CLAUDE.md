# LLM Quest DSPy Project Memory

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

## 最近提交
- feat: add testing framework and Excel processing utility
- feat: add GUI components and UI launcher scripts
- feat: add UI and audio processing dependencies
- feat: upgrade Docker environment and add entrypoint script
- fix: update speech recognition options count from 5 to 4

## 除錯和測試

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