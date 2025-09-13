# 對話邏輯一致性檢查系統實作計劃

## 📋 專案背景

基於 2025-09-12 的診斷測試發現，DSPy 對話系統存在邏輯一致性問題：
- **問題案例**: 第2輪回應「沒有發燒」，第3輪卻描述「發燒開始時間」
- **影響範圍**: 多輪對話的邏輯連貫性和醫療專業可信度
- **根本原因**: 缺乏對話歷史一致性檢查機制

## 🎯 實作目標

### 主要目標
1. **消除邏輯矛盾**: 檢測並防止前後不一致的醫療陳述
2. **保持系統穩定**: 零功能破壞，完全向後兼容
3. **性能可控**: 回應時間增加 ≤ 0.5秒
4. **品質提升**: 整體對話一致性提升 40%+

### 成功標準
- **檢出率**: ≥ 85% 邏輯矛盾檢出
- **誤報率**: ≤ 15%
- **兼容性**: 100% 現有功能完整保持
- **性能**: 多輪對話測試回應時間無顯著增長

## 📊 當前系統架構分析

### 核心檔案結構
```
src/core/dspy/
├── unified_dialogue_module.py          # 主要對話處理
├── optimized_dialogue_manager.py       # 會話管理
├── degradation_monitor.py              # 退化監控 (已實作)
└── [新增] consistency_checker.py       # 一致性檢查 (待實作)
```

### 對話流程分析
1. **輸入處理**: `OptimizedDialogueManagerDSPy.process_input()`
2. **歷史管理**: `conversation_history` List 格式
3. **回應生成**: `UnifiedDSPyDialogueModule.forward()` 
4. **品質監控**: `DegradationMonitor.assess_dialogue_quality()` (已有)

### 整合點識別
- **檢查時機**: 回應生成後，返回給用戶前
- **數據來源**: `conversation_history` + 新生成的 `responses`
- **整合位置**: `unified_dialogue_module.py` 第165行後

## 🚧 實作方案設計

### 方案選擇: 獨立檢查模組 (推薦)

**優勢**:
- 模組化設計，易於測試和維護
- 不影響現有 Signature 複雜度
- 可獨立配置和開關
- 便於未來擴展和優化

**架構**:
```python
# 新模組：consistency_checker.py
DialogueConsistencyChecker 
├── MedicalFactExtractor      # 醫療事實提取
├── ContradictionDetector     # 矛盾檢測
├── TimelineValidator        # 時間線驗證
└── ConsistencyScorer        # 一致性評分
```

## 📋 Phase 1: 基礎檢查模組建立

### 1.1 創建核心檔案 (預計時間: 1天)

#### 實作內容
1. **創建 `src/core/dspy/consistency_checker.py`**
   ```python
   class DialogueConsistencyChecker:
       def __init__(self):
           self.medical_fact_tracker = MedicalFactTracker()
           self.contradiction_detector = ContradictionDetector()
           self.timeline_validator = TimelineValidator()
       
       def check_consistency(self, new_responses: List[str], 
                           conversation_history: List[str],
                           character_context: Dict) -> ConsistencyResult:
           """主要一致性檢查方法"""
   ```

2. **醫療事實追蹤器**
   ```python
   class MedicalFactTracker:
       def __init__(self):
           self.facts = {
               'symptoms': {},           # 症狀狀態
               'timeline': [],           # 時間事件
               'physical_state': {},     # 身體狀態  
               'treatments': [],         # 治療記錄
               'vital_signs': {}         # 生命徵象
           }
   ```

3. **矛盾檢測器**
   ```python
   class ContradictionDetector:
       def __init__(self):
           self.contradiction_patterns = {
               'symptom_contradiction': [...],    # 症狀矛盾
               'timeline_inconsistency': [...],   # 時間不一致
               'state_mismatch': [...]           # 狀態不符
           }
   ```

#### 測試驗證 1.1
```bash
# 測試檔案: test_consistency_checker_basic.py
docker exec dialogue-server-jiawei-dspy python /app/test_consistency_checker_basic.py

# 驗證內容:
✅ 模組載入測試
✅ 基礎類別初始化測試  
✅ 醫療事實提取功能測試
✅ 簡單矛盾檢測測試
```

**成功標準**:
- 所有基礎功能單元測試通過
- 模組載入無錯誤
- 記憶體使用量 < 50MB

### 1.2 實作醫療事實提取 (預計時間: 1天)

#### 實作內容
1. **症狀狀態提取**
   ```python
   def extract_symptom_states(self, text: str) -> Dict[str, Any]:
       """提取症狀相關陳述"""
       patterns = {
           'fever': ['發燒', '體溫', '熱', '燒'],
           'pain': ['痛', '疼', '不舒服', '酸'],
           'swelling': ['腫', '脹', '腫脹']
       }
   ```

2. **時間線事件提取**
   ```python
   def extract_timeline_events(self, text: str) -> List[TimelineEvent]:
       """提取時間相關事件"""
       time_patterns = [
           r'昨天\w*開始',
           r'今天\w*',  
           r'\w*小時前',
           r'從\w*時候開始'
       ]
   ```

3. **醫療情境識別**
   ```python
   def identify_medical_context(self, text: str) -> str:
       """識別醫療情境類型"""
       contexts = {
           'pain_assessment': ['痛', '疼痛程度'],
           'fever_check': ['發燒', '體溫'],
           'recovery_status': ['恢復', '好轉', '改善']
       }
   ```

#### 測試驗證 1.2  
```bash
# 測試檔案: test_medical_fact_extraction.py
docker exec dialogue-server-jiawei-dspy python /app/test_medical_fact_extraction.py

# 測試案例:
案例1: "沒有發燒，但傷口有點痛" 
期待: fever=False, pain=True

案例2: "昨天晚上開始覺得有點熱"
期待: timeline=[昨晚發熱事件], fever=True

案例3: "大概是從今天早上開始"  
期待: timeline=[今早開始事件]
```

**成功標準**:
- 症狀提取準確率 ≥ 90%
- 時間線提取準確率 ≥ 85%
- 處理速度 < 0.1秒/句

### 1.3 實作矛盾檢測邏輯 (預計時間: 1天)

#### 實作內容
1. **症狀矛盾檢測**
   ```python
   def detect_symptom_contradictions(self, 
                                   previous_facts: Dict, 
                                   new_facts: Dict) -> List[Contradiction]:
       """檢測症狀前後矛盾"""
       contradictions = []
       
       # 發燒狀態矛盾
       if previous_facts.get('fever') is False and new_facts.get('fever') is True:
           contradictions.append(Contradiction(
               type='fever_state_flip',
               severity='high',
               description='前述無發燒，後續描述發燒症狀'
           ))
   ```

2. **時間線邏輯檢查**
   ```python
   def validate_timeline_logic(self, timeline_events: List[TimelineEvent]) -> List[Contradiction]:
       """驗證時間線邏輯"""
       # 檢查時間先後順序
       # 檢查事件間隔合理性
       # 檢查因果關係邏輯
   ```

3. **醫療邏輯驗證**
   ```python
   def check_medical_logic(self, medical_context: str, 
                          facts: Dict) -> List[Contradiction]:
       """檢查醫療邏輯合理性"""
       # 手術後症狀合理性
       # 恢復進程邏輯性
       # 治療反應一致性
   ```

#### 測試驗證 1.3
```bash
# 測試檔案: test_contradiction_detection.py  
docker exec dialogue-server-jiawei-dspy python /app/test_contradiction_detection.py

# 測試案例:
矛盾案例1: 第2輪"沒發燒" → 第3輪"昨晚開始發燒"
期待: 檢出發燒狀態矛盾

矛盾案例2: "今早開始痛" → "昨晚就開始了"  
期待: 檢出時間線矛盾

正常案例: "有點痛" → "還是有點痛"
期待: 無矛盾檢出
```

**成功標準**:
- 矛盾檢出率 ≥ 85%
- 誤報率 ≤ 15%
- 處理時間 < 0.2秒

**Phase 1 整體測試**
```bash
# 完整基礎功能測試
docker exec dialogue-server-jiawei-dspy python /app/test_consistency_module_complete.py

# 驗證內容:
✅ 所有基礎功能正常
✅ 無記憶體洩漏
✅ 錯誤處理完善
✅ 日誌記錄正確
```

## 📋 Phase 2: 整合到對話流程

### 2.1 整合到 UnifiedDSPyDialogueModule (預計時間: 1天)

#### 實作內容
1. **修改 `unified_dialogue_module.py`**
   ```python
   class UnifiedDSPyDialogueModule:
       def __init__(self, config: Optional[Dict[str, Any]] = None):
           # 現有初始化...
           
           # 新增: 一致性檢查器
           from .consistency_checker import DialogueConsistencyChecker
           self.consistency_checker = DialogueConsistencyChecker()
           self.enable_consistency_check = config.get('enable_consistency_check', True)
   ```

2. **在 forward() 方法中整合檢查**
   ```python
   def forward(self, ...):
       # 現有邏輯直到第165行 unified_prediction...
       
       # 新增: 一致性檢查
       if self.enable_consistency_check and len(conversation_history) >= 2:
           consistency_result = self._perform_consistency_check(
               responses=parsed_responses,
               conversation_history=conversation_history,
               character_info={
                   'name': character_name,
                   'persona': character_persona,
                   'medical_context': character_details
               }
           )
           
           # 根據檢查結果調整回應
           if consistency_result.has_contradictions:
               parsed_responses = self._handle_consistency_issues(
                   responses=parsed_responses,
                   consistency_result=consistency_result
               )
   ```

3. **實作處理邏輯**
   ```python
   def _perform_consistency_check(self, responses, conversation_history, character_info):
       """執行一致性檢查"""
       return self.consistency_checker.check_consistency(
           new_responses=responses,
           conversation_history=conversation_history,
           character_context=character_info
       )
   
   def _handle_consistency_issues(self, responses, consistency_result):
       """處理一致性問題"""
       if consistency_result.severity == 'high':
           # 高嚴重度：過濾矛盾回應
           return self._filter_contradictory_responses(responses, consistency_result)
       else:
           # 中低嚴重度：加入修正提示
           return self._add_consistency_hints(responses, consistency_result)
   ```

#### 測試驗證 2.1
```bash
# 測試檔案: test_integration_consistency.py
docker exec dialogue-server-jiawei-dspy python /app/test_integration_consistency.py

# 測試案例:
案例1: 正常多輪對話 (無一致性問題)
期待: 功能完全正常，無性能影響

案例2: 故意矛盾輸入測試
輸入: ["護理人員: 有發燒嗎？", "Patient_1: 沒有發燒", 
      "護理人員: 什麼時候開始發燒的？"]
期待: 檢測到矛盾，給出合理回應

案例3: 邊界情況測試
輸入: 空歷史、極長歷史、特殊字符
期待: 系統穩定，無崩潰
```

**成功標準**:
- 現有功能 100% 正常
- 矛盾檢測正確觸發
- 回應時間增加 < 0.3秒
- 無內存洩漏或錯誤

### 2.2 整合配置和開關機制 (預計時間: 0.5天)

#### 實作內容
1. **配置系統擴展**
   ```python
   # config/config.yaml 新增
   dspy:
     consistency_check:
       enabled: true
       strictness_level: "medium"  # low/medium/high
       medical_focus: true
       performance_mode: false     # 高性能模式關閉部分檢查
   ```

2. **運行時控制**
   ```python
   # 環境變數控制
   CONSISTENCY_CHECK_ENABLED=true
   CONSISTENCY_CHECK_LEVEL=medium
   ```

3. **日誌和監控整合**
   ```python
   # 整合到現有日誌系統
   logger.info(f"🔍 CONSISTENCY CHECK - Round {round_num}")
   logger.info(f"  ✅ Contradictions Found: {len(result.contradictions)}")
   logger.info(f"  📊 Consistency Score: {result.score:.3f}")
   logger.info(f"  ⏱️ Check Duration: {check_time:.3f}s")
   ```

#### 測試驗證 2.2
```bash
# 配置測試
docker exec dialogue-server-jiawei-dspy python /app/test_consistency_config.py

# 測試案例:
✅ enabled=false 時功能完全關閉
✅ strictness_level 各級別正常工作
✅ 配置錯誤時有合理默認值
✅ 環境變數優先級正確
```

**成功標準**:
- 所有配置選項正常工作
- 關閉時零性能影響
- 配置錯誤時系統不崩潰

## 📋 Phase 3: 驗證和優化

### 3.1 完整系統測試 (預計時間: 1天)

#### 測試內容
1. **回歸測試: 原有多輪對話品質**
   ```bash
   # 使用完全相同的測試序列
   docker exec dialogue-server-jiawei-dspy python /app/run_tests.py
   
   # 對比基準:
   原始測試結果 (2025-09-12):
   - 第1輪: 1.533s, 正常品質
   - 第2輪: 1.237s, 正常品質  
   - 第3輪: 1.902s, 邏輯矛盾 ← 重點檢查
   - 第4輪: 1.240s, 正常品質
   - 第5輪: 1.098s, 最佳品質
   
   期待結果:
   - 第1-2輪: 性能無影響
   - 第3輪: 消除邏輯矛盾，時間略增但 < 2.5s
   - 第4-5輪: 性能無影響
   ```

2. **一致性檢查效果驗證**
   ```bash
   docker exec dialogue-server-jiawei-dspy python /app/test_consistency_effectiveness.py
   
   # 矛盾場景測試:
   場景1: 發燒狀態前後矛盾
   場景2: 疼痛程度邏輯不符
   場景3: 時間線順序錯亂
   場景4: 治療效果矛盾
   
   期待: 檢出率 ≥ 85%, 誤報率 ≤ 15%
   ```

3. **性能基準測試**
   ```bash
   docker exec dialogue-server-jiawei-dspy python /app/test_performance_benchmark.py
   
   # 測試指標:
   - 單輪回應時間變化
   - 記憶體使用量變化
   - CPU 使用率影響
   - 併發處理能力
   
   期待: 所有指標增長 < 30%
   ```

#### 測試驗證 3.1
**成功標準**:
- ✅ 原有 5輪測試完全通過
- ✅ 第3輪邏輯矛盾消除
- ✅ 整體回應時間增加 ≤ 0.5s
- ✅ 一致性檢查功能正確
- ✅ 無功能回歸

### 3.2 逐輪分析工具更新 (預計時間: 0.5天)

#### 實作內容
1. **更新 `test_round_by_round_analysis.py`**
   ```python
   # 在品質評估中加入一致性分析
   def _perform_detailed_analysis(self, api_response, round_number, ...):
       # 現有分析...
       
       # 新增: 一致性分析
       if 'consistency_check_result' in api_response:
           consistency_data = api_response['consistency_check_result']
           analysis['consistency_analysis'] = {
               'score': consistency_data.get('score', 1.0),
               'contradictions_found': consistency_data.get('contradictions', []),
               'medical_facts_extracted': consistency_data.get('facts', {}),
               'timeline_events': consistency_data.get('timeline', [])
           }
   ```

2. **報告格式擴展**
   ```python
   # JSON 報告中增加一致性相關欄位
   "consistency_metrics": {
       "score": 0.95,
       "contradictions_detected": 0,
       "medical_facts_count": 3,
       "timeline_events_count": 2
   }
   ```

#### 測試驗證 3.2
```bash
docker exec dialogue-server-jiawei-dspy python /app/test_round_by_round_analysis.py

# 驗證內容:
✅ 新的一致性指標正確顯示
✅ 矛盾檢測結果準確記錄
✅ 報告格式完整無錯誤
✅ 向下兼容性保持
```

### 3.3 監控和警報系統 (預計時間: 0.5天)

#### 實作內容
1. **整合到 DegradationMonitor**
   ```python
   # 在 degradation_monitor.py 中加入一致性指標
   def assess_dialogue_quality(self, response_data, round_number, ...):
       # 現有評估...
       
       # 新增: 一致性評估
       consistency_score = self._assess_consistency_quality(response_data)
       
       # 更新品質計算
       overall_quality = self._calculate_overall_quality_score(
           # ... 現有參數
           consistency_score=consistency_score
       )
   ```

2. **警報規則擴展**
   ```python
   def _check_consistency_warnings(self, consistency_result, round_number):
       if consistency_result.score < 0.5:
           self.logger.warning(f"🔍 CONSISTENCY WARNING - Round {round_number}")
           self.logger.warning(f"  矛盾檢測: {len(consistency_result.contradictions)} 個問題")
           
           # 觸發退化事件
           self.degradation_events.append({
               'type': 'consistency_degradation',
               'round': round_number,
               'score': consistency_result.score,
               'contradictions': consistency_result.contradictions
           })
   ```

#### 測試驗證 3.3
```bash
docker exec dialogue-server-jiawei-dspy python /app/test_monitoring_integration.py

# 驗證內容:
✅ 一致性指標整合正確
✅ 警報觸發機制正常
✅ 退化監控功能擴展
✅ 日誌記錄格式統一
```

## 📈 最終驗證測試

### 完整系統測試
```bash
# 1. 基礎功能回歸測試
docker exec dialogue-server-jiawei-dspy python /app/run_tests.py

# 2. 診斷工具驗證
docker exec dialogue-server-jiawei-dspy python /app/test_round_by_round_analysis.py

# 3. 內部狀態檢查
docker exec dialogue-server-jiawei-dspy python /app/debug_dspy_internal_state.py

# 4. 一致性專項測試
docker exec dialogue-server-jiawei-dspy python /app/test_consistency_comprehensive.py
```

### 成功標準檢查清單
- [ ] **功能完整性**: 原有所有功能正常
- [ ] **邏輯一致性**: 第2-3輪矛盾問題解決
- [ ] **性能影響**: 回應時間增加 ≤ 0.5秒
- [ ] **檢測能力**: 矛盾檢出率 ≥ 85%
- [ ] **誤報控制**: 誤報率 ≤ 15%
- [ ] **系統穩定**: 無崩潰、內存洩漏等問題
- [ ] **配置靈活**: 可開關、可調節
- [ ] **監控整合**: 與現有監控系統無縫整合

## 📝 實施注意事項

### 開發原則
1. **向後兼容**: 每個變更都必須保持 API 兼容性
2. **可配置性**: 所有新功能都要可開關
3. **測試優先**: 先寫測試，再寫實現
4. **性能監控**: 每個階段都要測量性能影響
5. **逐步部署**: 可以分階段啟用功能

### 風險控制
1. **降級機制**: 一致性檢查失敗時回到原有流程
2. **性能保護**: 檢查時間超過閾值時自動跳過
3. **錯誤隔離**: 檢查模組錯誤不影響主流程
4. **監控告警**: 異常情況及時發現和處理

### 文檔更新
- 更新 API 文檔說明新功能
- 記錄配置選項和使用方法  
- 提供故障排除指南
- 更新測試和驗證流程

## 🎯 預期效果

### 量化指標
- **邏輯矛盾消除率**: ≥ 85%
- **誤報率控制**: ≤ 15%
- **性能影響**: 回應時間增加 ≤ 0.5秒
- **系統穩定性**: 無功能回歸
- **檢測覆蓋率**: 醫療事實一致性檢查 ≥ 90%

### 質化改善
- 消除「發燒狀態矛盾」等邏輯問題
- 提升醫療對話的專業可信度
- 增強多輪對話的邏輯連貫性
- 為用戶提供更一致的對話體驗
- 建立可擴展的一致性檢查框架

---

**總預計時間**: 5-6 天
**實施方式**: 按 Phase 順序，每階段完成後進行完整測試驗證
**成功標準**: 所有測試通過，功能和性能目標達成

---

> 附錄 A：精細化落地計畫與測試矩陣（新增）

## 🧭 範圍與目標（精確版）

- 目標：在不影響現有 API/回應格式的前提下，新增對話一致性檢查與修復（防自我介紹、醫療事實不一致、時間線錯亂），並提升第4–5輪退化表現。
- 範圍：在 DSPy 對話路徑內（`src/core/dspy/`），以規則為主、LLM 為輔的方式，新增一致性檢查模組，插入 `UnifiedDSPyDialogueModule` 產出後、回傳前的階段；同時提供可關閉的 feature toggle。
- 不做：不更動外部 API 契約（server 輸出鍵維持不變），不引入新外部依賴，不增加額外 LLM 請求（Phase 1），確保成本與延遲穩定。

## ✅ 成功與驗收標準（可量測）

- 矛盾檢出率 ≥ 85%，誤報率 ≤ 15%（以合成案例 + 回歸集驗證）
- 第4–5輪退化（自我介紹、CONFUSED、情境退化、單一回應）顯著下降（腳本 `test_dialogue_degradation.py` 指標下降）
- 整體平均回應時間增加 ≤ 0.5s
- 完整回歸測試與新增單元/整合測試全部通過

## 🗂️ 檔案與類別地圖（最小變更）

- 新增：`src/core/dspy/consistency_checker.py`
  - `class DialogueConsistencyChecker`
    - `check_consistency(new_responses: List[str], conversation_history: List[str], character_context: Dict) -> ConsistencyResult`
  - `class MedicalFactTracker`
  - `class TimelineValidator`
  - `class ContradictionDetector`
  - `@dataclass Contradiction(type: str, severity: str, description: str, evidence: Dict)`
  - `@dataclass TimelineEvent(type: str, when: str, norm_time: float)`
  - `@dataclass ConsistencyResult(score: float, has_contradictions: bool, contradictions: List[Contradiction], facts: Dict, timeline: List[TimelineEvent], severity: str)`

- 變更：`src/core/dspy/unified_dialogue_module.py`
  - 初始化注入 `DialogueConsistencyChecker`，新增 `enable_consistency_check` toggle（預設開啟，可由 config 覆寫）。
  - 在生成 `unified_prediction` 後、包裝 `final_prediction` 前，執行一致性檢查與回應修正；將結果摘要寫入 `processing_info['consistency']`。

- 可選（Phase 3）：`src/core/dspy/signatures.py` 新增 LLM 輔助摘要/一致性簽名（僅規劃，第一階段不上線）。

- 測試：
  - `tests/dspy/test_consistency_checker.py`（單元）
  - `tests/dspy/test_consistency_integration_unified.py`（整合，使用 stub/monkeypatch 避免 LLM 呼叫）
  - 保持既有：`tests/dspy/test_dialogue_module*.py`、腳本 `test_dialogue_degradation.py`（觀察整體改善）

## 🔧 Phase 0：腳手架與開關（0.5 天）

- 新增 `DialogueConsistencyChecker` 介面與資料類別（空實作/最小返回值），確保 import/初始化無副作用。
- 在 `src/core/dspy/unified_dialogue_module.py` 注入 checker 與 toggle：
  - `self.enable_consistency_check = config.get('enable_consistency_check', True)`
  - 當 `False` 時行為完全等同目前版本。
- 單元測試：`test_consistency_checker.py::test_bootstrap_noop` 驗證可初始化、可呼叫、返回 `ConsistencyResult` 型別。

## 🧪 Phase 1：規則版一致性核心（1 天）

重點：零額外 LLM 調用；純規則，快速可測。

- MedicalFactTracker（關鍵欄位）
  - fever/pain/swelling/meds/diet/sleep…（先以 fever/pain 為核心）
  - 時間語彙規範化：昨天/今天/幾小時前 → `norm_time`（float，越近越大）
  - API：`extract(text: str) -> Dict`、`extract_timeline(text: str) -> List[TimelineEvent]`

- ContradictionDetector
  - 症狀狀態翻轉：previous.feel.fever=False → new.feel.fever=True
  - 自我介紹檢測：包含「我是」「我叫」「我是Patient」等
  - 通用回應偵測：如「我可能沒有完全理解」「您需要什麼幫助」
  - API：`detect(previous_facts: Dict, new_facts: Dict, timeline: List[TimelineEvent]) -> List[Contradiction]`

- TimelineValidator
  - 檢查相鄰事件是否違反先後（今早 vs 昨晚）
  - API：`validate(timeline: List[TimelineEvent]) -> List[Contradiction]`

- Score 與 Severity
  - `score = 1 - min(1.0, 0.3*contradictions + 0.2*self_intro + 0.2*generic + 0.3*timeline)`
  - `severity`: `high`（阻擋/過濾）/`medium`（提示）/`low`（僅紀錄）

- 單元測試（純規則、可離線）：
  - `tests/dspy/test_consistency_checker.py`
    - fever 矛盾（無→有/高→無）
    - timeline 矛盾（今早→昨晚開始）
    - 自我介紹與通用回應檢出
    - 無矛盾時 `has_contradictions=False`、score≈1.0

## 🔗 Phase 2：整合 Unified 模組（1 天）

- 插入點（之後以實作行為為準）：
  - `src/core/dspy/unified_dialogue_module.py:173` 附近，`unified_prediction` 取得後、`final_prediction` 回傳前。
  - 處理流程：
    1) `parsed_responses = self._process_responses(unified_prediction.responses)`
    2) `consistency = self.consistency_checker.check_consistency(parsed_responses, conversation_history, {...})`
    3) `if consistency.has_contradictions: parsed_responses = self._apply_consistency_fixes(parsed_responses, consistency)`
    4) 將 `consistency` 摘要放入 `processing_info['consistency']`（例如：`{"score": 0.82, "contradictions": 1, "severity": "medium"}`）

- 修正策略（無二次 LLM 呼叫）：
  - high：移除矛盾回應；若全被移除，保留 1–2 則中性/禮貌回應（現有 fallback）
  - medium/low：在回應尾端附加 3–8 字的輕量提示（例如「（保持與先前陳述一致）」）

- 整合測試（避免 LLM）：`tests/dspy/test_consistency_integration_unified.py`
  - monkeypatch `UnifiedDSPyDialogueModule.unified_response_generator`（或 `response_generator`）返回可控 `Prediction`，其 `responses` 帶入矛盾樣本
  - 驗證：修正策略生效、`processing_info.consistency` 存在且數值合理、無例外

## 🧠 Phase 3（可選）：LLM 輔助摘要/檢查（0.5–1 天，預設關閉）

- 新增（預備）：
  - `ConversationSummarySignature`：將多輪歷史壓縮為重要事實摘要（避免長字串堆疊）
  - `ConsistencyCheckSignature`：在重大矛盾時，對矛盾處提出具體修復建議（僅提示，不自動覆寫）
- Toggle：`enable_llm_consistency_assist=False` 預設關閉
- 測試：同樣以 monkeypatch/stub 注入固定輸出，確保單元/整合測試 deterministic

## 📡 Phase 4：對外觀測與日誌（0.5 天）

- 在 `processing_info` 寫入一致性摘要（不更動頂層鍵）：
  - `processing_info['consistency'] = {'score': x, 'contradictions': n, 'severity': 'low|medium|high'}`
- 更新分析腳本（可選）：`test_round_by_round_analysis.py` 中將 `processing_info.consistency` 帶入報告（原文已有草案，沿用模式即可）

## 🧪 測試矩陣（對應檔案與重點）

- 單元：`tests/dspy/test_consistency_checker.py`
  - fever/pain 狀態矛盾、timeline 矛盾、自我介紹、通用回應、正常樣本
- 整合：`tests/dspy/test_consistency_integration_unified.py`
  - 無 LLM：以 stub `Prediction` 注入 responses 與 conversation_history
  - 驗證回應被過濾/提示、processing_info 寫入、一律不丟例外
- 回歸：沿用現有 `tests/dspy/*` 全套
- 端到端觀察：`test_dialogue_degradation.py`
  - 比對第4–5輪指標：自我介紹、CONFUSED、情境退化、單回應減少

### 指令（容器內/本機皆可對應）

```bash
# 單元/整合（CI 本地）
pytest -q tests/dspy/test_consistency_checker.py
pytest -q tests/dspy/test_consistency_integration_unified.py

# 舊有測試
pytest -q tests/dspy

# 端到端觀察（容器）
docker exec dialogue-server-jiawei-dspy python /app/test_dialogue_degradation.py
```

## ⏱️ 效能與配額預算

- Phase 1 僅規則運算，理論上 < 1ms/輪（CPU）；整體回應時間增加主要來自字串處理，預估 < 50ms
- 無額外 LLM 呼叫（維持 1 次/輪）
- 記憶體：儲存最近 N 輪摘要/事實，< 1MB

## 🧯 風險與回退

- 誤報造成過濾過度 → 嚴重度門檻微調、保留至少 1–2 則中性回應
- 規則覆蓋不足 → 以「提示模式」代替「過濾模式」降低破壞性
- 意外相容性問題 → 立即關閉 `enable_consistency_check`（預載於 config）

## 🚀 推出與驗收流程

1) 合併 Phase 0–1 + 測試通過 → 在開發環境跑 `test_dialogue_degradation.py` 拿基準
2) 觀察第4–5輪退化是否下降 → 若是，開 `enable_consistency_check=True` 進行試運行
3) 跑全測 + 回歸（`tests/dspy/` 與既有腳本）→ 無回歸後合併主分支

## 🧩 任務清單（可逐項完成打勾）

- [ ] 新增 `src/core/dspy/consistency_checker.py`（類別/資料結構 + 規則實作）
- [ ] `UnifiedDSPyDialogueModule` 注入 checker 與 toggle
- [ ] 將 `processing_info['consistency']` 寫入結果
- [ ] 單元測試：`tests/dspy/test_consistency_checker.py`
- [ ] 整合測試：`tests/dspy/test_consistency_integration_unified.py`
- [ ] 回歸測試：`tests/dspy/*`
- [ ] 端到端觀察：`test_dialogue_degradation.py`（第4–5輪品質）
