# LLM Quest Copilot

一個基於 LLM 的口腔癌病患對話系統，用於醫護人員訓練和評估。系統支援文字及語音輸入，並提供多重回應選項。

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
│   │   ├── logger.py        # 日誌功能
│   │   └── speech_input.py  # 語音輸入處理
│   ├── gui/                  # 圖形介面
│   │   └── chat_window.py    # 對話視窗
│   └── tests/                # 測試相關
│       └── test_scenarios/   # 測試情境
├── config/                   # 設定檔
│   ├── config.yaml          # 主要設定
│   ├── characters.yaml      # 病患角色設定
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
     input_mode: "voice"  # 可選值: "text" 或 "voice"
     save_recordings: false  # 是否保存錄音檔案
     debug_mode: false  # 是否顯示除錯訊息
     ```
   - dialogue_prompts.yaml 需包含：
     - character_response
     - evaluation_prompt
   - test_scenarios.yaml 需包含測試情境定義

## 執行方式

系統提供兩種操作模式，都通過 `gui_main.py` 啟動：

1. 終端機模式：
```bash
python gui_main.py --terminal
```
- 在終端機中進行對話
- 使用數字選擇病患
- 輸入文字進行對話
- 使用 'q' 或 'quit' 或 'exit' 結束對話
- 在選項中按 '0' 跳過當前回應
- 按 1-5 選擇對應的回應選項

2. 圖形化介面模式：
```bash
python gui_main.py
```
- 提供視窗化操作介面
- 點擊按鈕選擇病患
- 支援文字輸入和語音輸入：
  * 文字輸入：直接在輸入框輸入並按發送
  * 語音輸入：按住"按住說話"按鈕說話，放開自動辨識
- 系統會顯示多個回應選項按鈕：
  * 1-5 號按鈕對應不同的回應選項
  * 0 號按鈕用於跳過當前回應（當所有選項都不適合時）
- 選擇回應後系統會提示繼續提問

3. 執行自動化測試：
```bash
python run_tests.py
```

- google-generativeai：用於生成對話回應
- pyyaml：設定檔讀取
- tkinter：GUI介面（Python內建）
- speech_recognition：語音辨識
- pyaudio：音訊處理
- google-cloud-speech：Google語音辨識服務
- numpy：音訊數據處理
- python-dotenv：環境變數管理（可選）

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
   - 確認 Google API Key 設定正確
   - 檢查網路連接

3. 語音輸入問題：
   - 確認麥克風權限設定
   - 檢查音訊裝置設定
   - 確認 PyAudio 正確安裝

4. 檔案找不到：
   - 確保在正確的目錄執行
   - 檢查所有必要的設定檔是否存在

## License

MIT License 