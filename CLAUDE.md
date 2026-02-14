# LLM Quest Copilot - Dev Environment

## Docker 開發須知（重要）

**不要每次修改程式碼就跑 `docker compose up --build`！這非常耗時（5-15 分鐘）。**

本專案的 `docker-compose.yaml` 已設定 volume mount：
```yaml
volumes:
  - ./src:/app/src
  - ./config:/app/config
  - ./prompts:/app/prompts
  - ./run_ui.py:/app/run_ui.py
```

因此：
- **修改 `src/`、`config/`、`prompts/`**：不需要任何動作，程式碼即時同步到容器內。如果服務需要重新載入，只需 `docker restart llm-quest-copilot-dev`（幾秒鐘）。
- **只有修改 `Dockerfile`、`requirements.txt`** 等影響 Docker image layer 的檔案，才需要 `docker compose up -d --build`。

## Dev 環境資訊

| 項目 | 值 |
|------|-----|
| Container | `llm-quest-copilot-dev` |
| API Port | `18000`（外部）→ `8000`（內部） |
| UI Port | `17860`（外部）→ `7860`（內部） |
| 分支 | `dev` |

## 常用命令

```bash
# 檢查容器狀態
docker compose ps

# 查看 logs
docker compose logs app --tail=50

# 只重啟服務（不 rebuild）
docker restart llm-quest-copilot-dev

# 測試 API
curl http://localhost:18000/api/health/status

# 進入容器
docker exec -it llm-quest-copilot-dev bash
```
