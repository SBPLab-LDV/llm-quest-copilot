# DSPy 對話退化根本原因分析與追蹤操作手冊

## 📋 問題總覽

### 核心現象
DSPy 統一對話模組在多輪對話的第4-5輪出現系統性退化：
- ✅ 第1-3輪：正常對話，5個回應選項，適切的醫療情境
- 🔴 第4-5輪：自我介紹模式，單一回應，情境退化為"一般問診對話"

### 退化症狀詳細分析
1. **自我介紹模式**：`"您好，我是Patient_1，口腔癌病患"`
2. **通用回應模式**：`"我可能沒有完全理解您的問題"`
3. **回應數量異常**：從5個選項→1個選項
4. **情境退化**：從"醫師查房"、"身體評估"→"一般問診對話"
5. **角色記憶丟失**：忘記已建立的病患角色設定

## 🔍 根本原因假設

### 主要假設 1: DSPy ChainOfThought 推理穩定性問題
**技術分析**：
- `dspy.ChainOfThought(UnifiedPatientResponseSignature)` 在複雜場景下推理不穩定
- LLM 模型在處理多輸入多輸出的複雜 Signature 時容易產生認知負荷
- Chain of Thought 推理路徑在長對話中累積錯誤

**證據**：
- 退化總是出現在第4-5輪（認知負荷閾值）
- 回應時間急劇縮短（6-8s → 0.7-3s），表示推理過程簡化
- 單一回應而非多選項，顯示推理複雜度降低

### 主要假設 2: Signature 設計過於複雜
**技術分析**：
```python
class UnifiedPatientResponseSignature(dspy.Signature):
    # 8個輸入欄位
    user_input, character_name, character_persona, character_backstory, 
    character_goal, character_details, conversation_history, available_contexts
    
    # 7個輸出欄位
    reasoning, character_consistency_check, context_classification, 
    confidence, responses, state, dialogue_context, state_reasoning
```
- 15個欄位的複雜度可能超過 LLM 的穩定處理能力
- 多個約束條件在長對話中可能產生衝突
- 統一處理增加了單一失敗點的風險

### 主要假設 3: 對話歷史累積效應
**技術分析**：
- 第4輪後對話歷史包含 6-8 個條目
- 複雜的歷史格式可能干擾 LLM 的角色記憶
- 上下文窗口限制導致重要的角色設定信息被擠出

**證據**：
- 相同輸入重複測試在第2次就開始退化
- 情境從具體醫療場景退化為通用場景
- 角色設定丟失，回到預訓練的通用助手模式

### 次要假設 4: LLM 模型本身的限制
- 特定模型在多輪角色扮演中的固有限制
- Token 使用量增長導致的品質下降
- 模型對繁體中文醫療對話的特化能力不足

## 📊 追蹤和診斷操作手冊

### Phase 1: 建立深度日誌追蹤系統

#### 1.1 DSPy 內部狀態追蹤
**操作步驟**：
1. 修改 `src/core/dspy/unified_dialogue_module.py`
2. 在 `unified_response_generator` 調用前後加入狀態日誌
3. 執行測試並分析 DSPy 內部變化

**關鍵日誌點**：
```python
# 調用前狀態
logger.info("=== DSPy INTERNAL STATE PRE-CALL ===")
logger.info(f"🧠 Model State: {self.unified_response_generator.lm}")
logger.info(f"📊 Success Rate: {self.get_success_rate()}")
logger.info(f"🔄 Total Calls: {self.stats['total_calls']}")

# 調用後狀態
logger.info("=== DSPy INTERNAL STATE POST-CALL ===")  
logger.info(f"💭 Token Usage: {self._estimate_token_usage()}")
logger.info(f"🎯 Prediction Quality: {self._assess_prediction_quality()}")
```

**測試命令**：
```bash
docker exec dialogue-server-jiawei-dspy python /app/test_dialogue_degradation.py > dspy_internal_trace.log 2>&1
```

#### 1.2 LLM 推理過程深度追蹤
**操作步驟**：
1. 創建推理品質評估函數
2. 記錄完整的 reasoning 輸出
3. 分析推理品質在各輪次的變化

**實現方法**：
```python
def _trace_llm_reasoning(self, prediction, round_number):
    logger.info(f"=== LLM REASONING TRACE - Round {round_number} ===")
    logger.info(f"💭 Full Reasoning: {prediction.reasoning}")
    logger.info(f"✅ Consistency Check: {prediction.character_consistency_check}")
    
    # 推理品質分析
    quality_score = self._calculate_reasoning_quality(prediction.reasoning)
    logger.info(f"📊 Reasoning Quality Score: {quality_score}")
```

#### 1.3 會話狀態變化追蹤
**操作步驟**：
1. 修改 `optimized_dialogue_manager.py`
2. 在每輪對話後記錄會話狀態變化
3. 追蹤角色一致性分數的變化

**關鍵指標**：
- 對話歷史長度變化
- 角色一致性分數
- 回應品質指標
- 上下文相關性

### Phase 2: 建立退化預警系統

#### 2.1 創建退化監控系統
**檔案**: `src/core/dspy/degradation_monitor.py`

**操作步驟**：
1. 創建監控類別
2. 實現實時品質評估
3. 設置退化預警閾值

**使用方法**：
```python
monitor = DegradationMonitor()
quality_score = monitor.assess_dialogue_quality(response_data, round_number)
if quality_score < 0.7:
    logger.warning(f"🚨 Degradation risk detected: score={quality_score}")
```

#### 2.2 建立品質指標系統
**關鍵指標**：
- Character Consistency Score (0-1)
- Response Relevance Score (0-1)  
- Context Appropriateness Score (0-1)
- Self-Introduction Detection (boolean)
- Generic Response Detection (boolean)

### Phase 3: 建立診斷測試工具

#### 3.1 逐輪分析工具
**檔案**: `test_round_by_round_analysis.py`

**功能**：
- 記錄每輪的詳細狀態
- 生成推理過程變化報告
- 識別退化開始的精確時點

**執行命令**：
```bash
docker exec dialogue-server-jiawei-dspy python /app/test_round_by_round_analysis.py
```

#### 3.2 DSPy 內部狀態檢查工具
**檔案**: `debug_dspy_internal_state.py`

**功能**：
- 檢查 DSPy 模型參數
- 分析 ChainOfThought 推理路徑
- 監控 LLM 調用的詳細資訊

#### 3.3 對話歷史影響分析工具
**檔案**: `test_conversation_history_impact.py`

**功能**：
- 測試不同長度對話歷史的影響
- 驗證上下文重置機制
- 分析最佳歷史長度

### Phase 4: 根本原因驗證實驗

#### 4.1 簡化 Signature 實驗
**目標**: 驗證 Signature 複雜度假設

**實驗設計**：
1. 創建簡化版 Signature（3輸入，3輸出）
2. 對比測試退化情況
3. 分析複雜度對穩定性的影響

**檔案**: `test_simplified_signature.py`

#### 4.2 分段處理對比實驗
**目標**: 驗證統一處理 vs 分段處理

**實驗設計**：
1. 恢復原始的分段處理模式
2. 對比統一處理和分段處理的穩定性
3. 分析 API 調用次數與品質的權衡

**檔案**: `test_staged_processing.py`

#### 4.3 上下文長度優化實驗
**目標**: 找出最佳對話歷史長度

**實驗設計**：
1. 測試 1-10 輪不同歷史長度
2. 分析每個長度的退化率
3. 找出穩定性和資訊量的最佳平衡點

**檔案**: `test_context_length_optimization.py`

## 🔧 實施時程

### Week 1: 建立追蹤系統
- Day 1-2: Phase 1.1-1.3 日誌系統
- Day 3-4: Phase 2.1-2.2 監控系統  
- Day 5: 初步測試和調試

### Week 2: 診斷工具開發
- Day 1-2: Phase 3.1-3.2 診斷工具
- Day 3-4: Phase 3.3 歷史影響分析
- Day 5: 工具整合和測試

### Week 3: 根本原因驗證
- Day 1-2: Phase 4.1-4.2 實驗設計
- Day 3-4: Phase 4.3 最佳化實驗
- Day 5: 結果分析和報告

## 📈 成功標準

### 定量指標
1. **精確定位退化時點**：能夠確定退化發生在第幾輪的第幾次 LLM 調用
2. **量化退化因素**：能夠測量不同因素對退化的影響權重
3. **預測退化風險**：建立退化風險評估模型，準確率 > 90%
4. **改善建議驗證**：測試不同解決方案的效果改善程度

### 定性目標
1. **深度理解 DSPy 機制**：了解 ChainOfThought 在複雜場景下的行為
2. **建立預防機制**：創建可以預防類似問題的監控系統
3. **優化架構設計**：提供基於實證的架構改進建議
4. **知識文檔化**：建立完整的問題分析和解決方案文檔

## 📝 操作檢查清單

### 開始前準備
- [ ] 確認 Docker 容器運行正常
- [ ] 備份現有代碼
- [ ] 設置詳細日誌級別
- [ ] 準備測試環境

### Phase 1 執行檢查
- [ ] DSPy 內部狀態日誌正常記錄
- [ ] LLM 推理過程追蹤完整
- [ ] 會話狀態變化記錄詳細
- [ ] 日誌文件大小和格式合理

### Phase 2 執行檢查  
- [ ] 退化監控系統運作正常
- [ ] 品質指標計算準確
- [ ] 預警機制觸發及時
- [ ] 監控數據完整保存

### Phase 3 執行檢查
- [ ] 逐輪分析工具輸出詳細
- [ ] DSPy 內部狀態檢查完整
- [ ] 對話歷史影響分析清晰
- [ ] 所有測試工具正常運行

### Phase 4 執行檢查
- [ ] 簡化 Signature 實驗結果明確
- [ ] 分段處理對比實驗完整
- [ ] 上下文長度優化實驗全面
- [ ] 實驗結果可重現

## 🚨 注意事項

### 測試執行注意事項
1. **日誌文件管理**：定期清理，避免磁盤空間不足
2. **性能影響**：詳細日誌可能影響回應時間
3. **測試隔離**：確保測試不互相影響
4. **結果保存**：所有重要結果都要保存到文件

### 分析注意事項
1. **數據客觀性**：避免確認偏誤，客觀分析所有數據
2. **多次驗證**：重要發現需要多次實驗驗證
3. **邊界情況**：特別注意極端和邊界情況
4. **系統性思考**：從系統角度而非局部角度分析問題

這個操作手冊將指導我們系統性地找出 DSPy 對話退化的根本原因，並建立長期的預防和監控機制。