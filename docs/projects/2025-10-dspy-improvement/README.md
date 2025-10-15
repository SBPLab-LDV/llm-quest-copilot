**2025-10 DSPy 對話系統改善專案**

目的：集中追蹤本次系統改善的所有說明文件與計畫，統一版本控制，便於後續回溯與驗證。

—

內容索引
- 01_issue_mapping.md：內部測試問題 × DSPy 簽名/模組 映射與因子分析（口語表達 vs 文字回答）。
- 02_plan_audio_disfluency.md：口語表達（ASR→句子選項）改善規劃（前/後差異與推理鏈）。
- 03_plan_audio_keyword_alignment_minimal.md：極簡規劃（僅調整提示文本），專注「嗆到，想回家。」關鍵詞對齊與避免泛用無關句。
- 參考資料（未搬移）：
  - 測試彙整：`docs/test_scenarios/test.md`
  - 測試 PDF：`docs/test_scenarios/溝通小幫手內部測試問題整理.pdf`

—

使用說明
- 本資料夾內各 md 為本次改善專案的「單一真實來源」。若有更新，請優先修改這裡並在 commit message 附上測試步驟與結果。
- 日誌（logs/）仍依專案規範由 Git LFS 管理，請勿搬移進本資料夾。
