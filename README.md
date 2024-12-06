# LLM Quest Copilot

一個基於 LLM 的 NPC 對話測試系統，用於評估 NPC 的回應品質和對話連貫性。

## 專案結構

```
llm-quest-copilot/
├── src/                      # 源代碼
│   ├── core/                 # 核心功能
│   │   ├── character.py      # 病患定義
│   │   ├── dialogue.py       # 對話管理
│   │   └── state.py         # 狀態管理
│   ├── llm/                  # LLM 相關
│   │   └── gemini_client.py  # Gemini API 客戶端
│   ├── utils/                # 工具函數
│   │   ├── config.py        # 設定檔讀取
│   │   └── logger.py        # 日誌功能
│   ├── gui/                  # 圖形介面
│   │   └── chat_window.py    # 對話視窗
│   └── tests/                # 測試相關
│       └── test_scenarios/   # 測試情境
├── config/                   # 設定檔
│   ├── config.yaml          # 主要設定
│   └── test_scenarios.yaml  # 測試情境設定
├── prompts/                  # 提示詞模板
│   └── dialogue_prompts.yaml
└── logs/                    # 日誌檔案
```

## 安裝步驟

1. 克隆專案：
```bash
git clone https://github.com/yourusername/llm-quest-copilot.git
cd llm-quest-copilot
```

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

3. 設定 API Key：
```bash
# 複製設定檔範例
cp config.example.yaml config/config.yaml

# 編輯 config/config.yaml，填入你的 Google API Key
```

## 設定檔準備

1. 確保以下檔案存在且格式正確：
   - `config/config.yaml`：包含 Google API Key
   - `prompts/dialogue_prompts.yaml`：包含對話提示詞
   - `config/test_scenarios.yaml`：包含測試情境

2. 檢查設定檔格式：
   - config.yaml:
     ```yaml
     google_api_key: "your-api-key-here"
     ```
   - dialogue_prompts.yaml 需包含：
     - character_response
     - evaluation_prompt
   - test_scenarios.yaml 需包含測試情境定義

## 執行方式

1. 命令列介面：
```bash
python main.py
```
- 在終端機中進行對話
- 使用數字選擇病患
- 輸入文字進行對話
- 使用 'quit' 或 'exit' 結束對話

2. 圖形化介面：
```bash
python gui_main.py
```
- 提供視窗化操作介面
- 點擊按鈕選擇病患
- 在文字框輸入對話
- 關閉視窗結束對話

3. 執行自動化測試：
```bash
python run_tests.py
```

2. 查看測試結果：
   - 控制台輸出會顯示即時測試進度
   - 詳細日誌保存在 `logs/` 目錄下

## 測試結果說明

測試結果包含以下指標：
- 語意相關性：回應與當前情境的相關程度
- 目標一致性：是否符合病患設定
- 時序連貫性：與對話脈絡的連貫程度
- 回應適當性：回應的整體合適程度

## 注意事項

1. 確保已安裝所有必要的 Python 套件
2. 確保 Google API Key 有效且有足夠的配額
3. 執行時需要在專案根目錄
4. 檢查日誌檔案以獲取詳細的執行資訊

## 依賴套件

- google-generativeai
- pyyaml
- tkinter (GUI介面，Python內建)
- python-dotenv (可選)

## 開發指南

1. 添加新的測試情境：
   - 在 `config/test_scenarios.yaml` 中定義新的情境
   - 遵循現有的格式添加互動內容

2. 修改提示詞：
   - 編輯 `prompts/dialogue_prompts.yaml`
   - 確保保持必要的格式化參數

3. 自定義評估指標：
   - 修改 `src/tests/test_runner.py` 中的評估邏輯
   - 更新 DeviationMetrics 資料類別

4. 自定義GUI介面：
   - 修改 `src/gui/chat_window.py`
   - 可以調整視窗大小、樣式和功能

## 疑難排解

1. ImportError:
   - 確保所有 `__init__.py` 檔案都已創建
   - 檢查 Python 路徑設定

2. API 錯誤：
   - 確認 API Key 設定正確
   - 檢查網路連接

3. 檔案找不到：
   - 確保在正確的目錄執行
   - 檢查所有必要的設定檔是否存在

## License

MIT License 