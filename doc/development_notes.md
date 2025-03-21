# 開發筆記

## 重構動機

原始程式碼存在以下問題：
1. 所有功能都集中在單一檔案 (NPC.py)，造成維護困難
2. 設定和提示詞寫死在程式碼中，不易修改和管理
3. 缺乏適當的錯誤處理和日誌記錄
4. 測試邏輯與核心功能混在一起

## 重構目標

1. **模組化設計**
   - 將不同功能拆分到獨立模組
   - 建立清晰的目錄結構
   - 提高程式碼的可維護性和可讀性

2. **設定外部化**
   - 將 API Key 移至設定檔
   - 將提示詞模板獨立管理
   - 將測試情境設定外部化

3. **改進測試架構**
   - 分離測試邏輯與核心功能
   - 增加測試結果的可視化
   - 提供更詳細的評估指標

4. **增強錯誤處理**
   - 添加適當的錯誤處理機制
   - 實作日誌功能
   - 提供更好的錯誤提示

## 目錄結構說明

```
llm-quest-copilot/
├── src/                    # 源代碼目錄
│   ├── core/              # 核心功能模組
│   │   ├── character.py   # 病患相關
│   │   ├── dialogue.py    # 對話管理
│   │   └── state.py       # 狀態管理
│   ├── llm/               # LLM 相關功能
│   ├── utils/             # 工具函數
│   └── tests/             # 測試相關
├── config/                # 設定檔目錄
├── prompts/              # 提示詞模板
└── doc/                  # 文檔目錄
```

## 主要改進

1. **核心功能模組化**
   - Character: 病患基本資訊管理
   - DialogueManager: 對話流程控制
   - DialogueState: 狀態定義和轉換

2. **設定管理改進**
   - config.yaml: API Key 和其他設定
   - dialogue_prompts.yaml: 提示詞模板
   - test_scenarios.yaml: 測試情境定義

3. **測試功能強化**
   - 自動化測試流程
   - 詳細的評估指標
   - 測試結果報告

4. **新增功能**
   - 日誌記錄
   - 錯誤處理
   - 設定檔驗證

## 待改進項目

1. **測試覆蓋**
   - 添加單元測試
   - 增加整合測試
   - 提供測試覆蓋率報告

2. **文檔完善**
   - API 文檔
   - 使用說明
   - 開發指南

3. **功能擴展**
   - 支援更多 LLM 模型
   - 增加更多評估指標
   - 提供 Web 介面

4. **效能優化**
   - 快取機制
   - 非同步處理優化
   - 記憶體使用優化

## 注意事項

1. **設定檔管理**
   - config.yaml 不應提交到版本控制
   - 保持 config.example.yaml 更新
   - 確保設定檔格式一致

2. **程式碼品質**
   - 遵循 PEP 8 規範
   - 添加適當的註釋
   - 保持程式碼簡潔

3. **版本控制**
   - 使用有意義的提交訊息
   - 保持適當的分支管理
   - 定期更新文檔

## 下一步計劃

1. 完善單元測試
2. 添加更多評估指標
3. 改進錯誤處理機制
4. 優化提示詞模板
5. 添加更多測試情境
6. 實作快取機制

## 參考資料

- [Google Generative AI 文檔](https://ai.google.dev/)
- [Python 最佳實踐指南](https://docs.python-guide.org/)
- [asyncio 文檔](https://docs.python.org/3/library/asyncio.html) 