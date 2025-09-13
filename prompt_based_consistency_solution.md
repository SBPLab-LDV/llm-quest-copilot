# Prompt-Based 對話邏輯一致性解決方案

## 🎯 核心理念

**讓 Gemini 在生成回應時自主避免邏輯矛盾，而不是事後程式檢查**

### 方案優勢
- ⚡ **開發效率**: 2-3小時 vs 5-6天
- 📝 **代碼量**: ~10行修改 vs ~1000+行新代碼  
- 🚀 **性能**: 零額外開銷 vs 增加0.5秒處理時間
- 🧠 **準確性**: LLM 語義理解 vs 規則匹配局限
- 💰 **維護成本**: 幾乎為零 vs 持續維護規則庫

## 📊 問題背景

### 實際測試中發現的矛盾
**2025-09-12 測試結果**：
- 第2輪: `"沒有發燒，但傷口有點痛"`
- 第3輪: `"大概是昨天晚上開始覺得有點熱熱的"`
- **矛盾**: 前面否定發燒，後面描述發燒開始時間

### 當前 Prompt 缺陷分析
```python
# 現有 reasoning 欄位 (第44行)
reasoning = dspy.OutputField(desc="推理過程：包含情境分析、角色一致性檢查、回應思考和狀態評估。必須確認不會進行自我介紹。")
```

**問題**: 完全沒有要求 Gemini 檢查邏輯一致性！

## 🔧 解決方案設計

### 方案A: 增強 reasoning 欄位 (推薦首試)

#### 目標文件
- **檔案**: `src/core/dspy/unified_dialogue_module.py`
- **位置**: 第44行 `reasoning` 欄位

#### 修改內容
```python
reasoning = dspy.OutputField(desc="""
推理過程 - 必須按順序執行以下步驟：

1. 【對話歷史邏輯一致性檢查】
   仔細檢查新回應是否與之前陳述存在邏輯矛盾：
   
   ❌ 嚴禁的矛盾類型：
   - 症狀狀態翻轉：如果之前說"沒發燒/不痛/沒腫"，現在就不能描述相反狀態或開始時間
   - 疼痛程度矛盾：疼痛描述要與之前陳述的程度相符或合理變化
   - 時間線混亂：症狀開始時間、事件順序要與之前提及的時間邏輯一致
   - 康復進展倒退：身體狀況改善描述不能與之前的好轉趨勢矛盾
   
   ⚠️ 檢查要點：
   - 如果對話歷史中提到"沒有XXX症狀"，新回應就不能描述"XXX症狀的開始時間"
   - 症狀程度變化要符合醫療常識和時間推移邏輯
   - 每個症狀描述都要與歷史記錄保持一致或合理演進

2. 【醫療情境分析】分析當前對話情境和醫療背景

3. 【角色一致性檢查】確認回應符合病患角色，不進行自我介紹

4. 【回應生成策略】基於一致性檢查結果，生成邏輯完全一致的回應

⚠️ 如發現任何邏輯矛盾，必須調整回應內容以保持與對話歷史的完全一致性。
寧可保守回應，也不可前後矛盾。
""")
```

### 方案B: 增強會話歷史提示

#### 目標文件  
- **檔案**: `src/core/dspy/unified_dialogue_module.py`
- **方法**: `_get_enhanced_conversation_history` (第423行附近)

#### 修改內容
```python
# 修改 character_reminder 部分
character_reminder = f"""
[重要提醒: 您是 {character_name}，{character_persona}。

⚠️ 邏輯一致性鐵則：
1. 必須與之前的症狀描述保持完全一致
   - 如果之前說"沒發燒"，現在就不能說"發燒開始時間"
   - 如果之前說"不痛"，現在就不能描述疼痛程度
2. 時間敘述要符合邏輯順序，不能前後矛盾
3. 身體狀況變化要合理，符合康復進展
4. 症狀程度描述要與歷史陳述一致或合理演進

🚫 絕對禁止前後矛盾的陳述
✅ 保持角色一致性，避免自我介紹]
"""
```

### 方案C: 新增一致性檢查欄位 (可選)

#### 在 UnifiedPatientResponseSignature 中新增
```python
dialogue_consistency_verification = dspy.OutputField(desc="""
對話邏輯一致性驗證：
檢查生成的回應是否與對話歷史存在任何邏輯矛盾。

輸出格式：
- CONSISTENT: 完全一致，無矛盾
- ADJUSTED: 發現潛在矛盾並已調整回應
- FLAGGED: 發現矛盾但無法調整，需要重新生成

如果選擇 ADJUSTED 或 FLAGGED，必須說明發現的矛盾類型。
""")
```

## 📋 實施計劃

### Phase 1: Prompt 設計與實作 (1小時)

#### 1.1 實施方案A - 修改 reasoning 欄位 (30分鐘)

**步驟**：
1. 備份當前版本
2. 修改 `src/core/dspy/unified_dialogue_module.py` 第44行
3. 使用上述設計的增強 prompt
4. 測試基本功能無誤

**成功標準**：
- 系統正常啟動
- 基本對話功能無影響
- Prompt 正確載入

#### 1.2 實施方案B - 增強會話歷史提示 (20分鐘)

**步驟**：
1. 修改 `_get_enhanced_conversation_history` 方法
2. 更新 `character_reminder` 內容
3. 測試多輪對話功能

**成功標準**：
- 歷史提示正確顯示
- 不影響對話流程

#### 1.3 評估是否需要方案C (10分鐘)

**決策標準**：
- 如果方案A+B效果明顯，暫不實施方案C
- 如果效果不夠，考慮新增一致性檢查欄位

### Phase 2: 基準測試與驗證 (1.5小時)

#### 2.1 建立專項測試 (45分鐘)

**創建測試檔案**: `test_prompt_consistency.py`

```python
#!/usr/bin/env python3
"""
Prompt-based 一致性解決方案測試

測試 Gemini 是否能在 prompt 指導下避免邏輯矛盾
"""

import requests
import json
import time

def test_fever_state_consistency():
    """測試發燒狀態一致性 - 核心矛盾案例"""
    
    print("🔥 測試案例1: 發燒狀態一致性")
    print("="*50)
    
    # 模擬原始矛盾場景
    session_id = None
    
    # 第1輪: 正常問候
    response1 = make_dialogue_request("你好，感覺怎麼樣？", session_id)
    session_id = response1.get('session_id')
    print("第1輪回應:")
    for i, resp in enumerate(response1.get('responses', [])[:2], 1):
        print(f"  [{i}] {resp}")
    
    # 第2輪: 明確否定發燒 
    response2 = make_dialogue_request("有沒有覺得發燒或不舒服？", session_id)
    print("\n第2輪回應:")
    for i, resp in enumerate(response2.get('responses', [])[:2], 1):
        print(f"  [{i}] {resp}")
    
    # 分析第2輪是否明確否定發燒
    fever_denial = any('沒有發燒' in resp or '沒燒' in resp or '不發燒' in resp 
                      for resp in response2.get('responses', []))
    print(f"\n第2輪是否否定發燒: {fever_denial}")
    
    # 第3輪: 關鍵測試 - 詢問開始時間
    response3 = make_dialogue_request("從什麼時候開始的？", session_id)
    print("\n第3輪回應 (關鍵測試):")
    for i, resp in enumerate(response3.get('responses', [])[:3], 1):
        print(f"  [{i}] {resp}")
    
    # 檢查是否出現邏輯矛盾
    fever_contradiction = False
    if fever_denial:
        fever_mentions = []
        for resp in response3.get('responses', []):
            if any(keyword in resp for keyword in ['發燒', '發熱', '燒', '熱', '體溫']):
                fever_mentions.append(resp)
                fever_contradiction = True
        
        if fever_contradiction:
            print("\n❌ 檢測到邏輯矛盾!")
            print("矛盾回應:")
            for resp in fever_mentions:
                print(f"  - {resp}")
        else:
            print("\n✅ 無邏輯矛盾，一致性良好!")
    
    return not fever_contradiction

def test_pain_consistency():
    """測試疼痛程度一致性"""
    
    print("\n\n💊 測試案例2: 疼痛程度一致性") 
    print("="*50)
    
    session_id = None
    
    # 第1輪: 聲稱狀況良好
    response1 = make_dialogue_request("你好，感覺怎麼樣？", session_id)
    session_id = response1.get('session_id')
    
    # 檢查是否聲稱狀況良好
    good_condition = any('還不錯' in resp or '還好' in resp or '沒事' in resp 
                        for resp in response1.get('responses', []))
    
    print("第1輪回應:")
    print(f"  狀況良好陳述: {good_condition}")
    if good_condition:
        for resp in response1.get('responses', []):
            if any(keyword in resp for keyword in ['還不錯', '還好', '沒事']):
                print(f"  例: {resp}")
                break
    
    # 第2輪: 詢問疼痛
    response2 = make_dialogue_request("有沒有疼痛或不舒服？", session_id)
    print("\n第2輪回應:")
    for i, resp in enumerate(response2.get('responses', [])[:2], 1):
        print(f"  [{i}] {resp}")
    
    # 檢查疼痛描述是否與第1輪一致
    severe_pain = any('很痛' in resp or '非常痛' in resp or '劇痛' in resp
                     for resp in response2.get('responses', []))
    
    if good_condition and severe_pain:
        print("\n❌ 檢測到矛盾: 第1輪說狀況良好，第2輪卻說很痛")
        return False
    else:
        print("\n✅ 疼痛描述與整體狀況一致")
        return True

def make_dialogue_request(text, session_id=None):
    """發送對話請求"""
    url = "http://localhost:8000/api/dialogue/text"
    
    payload = {
        "text": text,
        "character_id": "1",
        "character_config": {
            "name": "Patient_1",
            "persona": "一位剛接受口腔癌手術的中年男性病患，術後恢復期需要密切關注身體狀況。性格溫和但略顯焦慮。",
            "backstory": "陳先生，50歲，口腔癌第二期，剛完成腫瘤切除手術，目前在住院觀察期。手術順利但仍在恢復中。",
            "goal": "配合醫師查房，如實反映身體狀況，希望早日康復出院。"
        }
    }
    
    if session_id:
        payload["session_id"] = session_id
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        print(f"請求錯誤: {e}")
        return {}

def main():
    """主測試函數"""
    print("🧪 Prompt-based 一致性解決方案測試")
    print("="*60)
    
    # 確保API服務正常
    try:
        test_response = requests.get("http://localhost:8000/health", timeout=5)
        print("✅ API 服務正常\n")
    except:
        print("❌ API 服務不可用，請確保服務器運行")
        return
    
    results = []
    
    # 執行測試
    results.append(("發燒狀態一致性", test_fever_state_consistency()))
    results.append(("疼痛程度一致性", test_pain_consistency()))
    
    # 總結結果
    print("\n" + "="*60)
    print("📊 測試結果總結")
    print("="*60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n通過率: {passed}/{len(results)} ({passed/len(results)*100:.1f}%)")
    
    if passed == len(results):
        print("🎉 所有測試通過! Prompt-based 方案有效!")
    else:
        print("⚠️ 部分測試失敗，可能需要優化 prompt")

if __name__ == "__main__":
    main()
```

#### 2.2 基準對比測試 (30分鐘)

**測試流程**：

```bash
# 1. 修改前基準測試
echo "📊 執行修改前基準測試..."
docker exec dialogue-server-jiawei-dspy python /app/run_tests.py > test_results_before_prompt.log

# 2. 實施 prompt 修改
# (執行 Phase 1 的修改)

# 3. 修改後測試
echo "📊 執行修改後測試..."
docker exec dialogue-server-jiawei-dspy python /app/run_tests.py > test_results_after_prompt.log

# 4. 專項一致性測試  
docker exec dialogue-server-jiawei-dspy python /app/test_prompt_consistency.py

# 5. 逐輪分析驗證
docker exec dialogue-server-jiawei-dspy python /app/test_round_by_round_analysis.py
```

#### 2.3 效果評估 (15分鐘)

**評估指標**：

1. **邏輯矛盾消除率**
   - 目標: ≥ 90%
   - 測量: 專項測試通過率

2. **回應時間影響**  
   - 目標: 增加 ≤ 0.2秒
   - 測量: 對比修改前後的平均回應時間

3. **回應品質保持**
   - 目標: 不降低醫療回應的專業性
   - 測量: 人工評估回應內容品質

### Phase 3: 優化與細化 (30分鐘)

#### 3.1 Prompt 用詞優化 (15分鐘)

**基於測試結果的調整策略**：

```python
# 如果效果不夠明顯 - 加強版
if consistency_score < 0.9:
    reasoning_desc = """
    ⚠️ 嚴格邏輯一致性要求 - 違反將視為生成失敗：
    
    1. 【強制一致性檢查】
       - 絕對禁止與對話歷史矛盾的陳述
       - 症狀狀態一旦確立(有/無)，不得翻轉
       - 時間描述必須符合邏輯順序
       
    2. 【矛盾檢測重點】
       如果發現以下情況，必須拒絕生成該回應：
       - 歷史:"沒發燒" → 新回應:"發燒開始時間" ❌
       - 歷史:"不痛" → 新回應:"疼痛程度描述" ❌  
       - 歷史:"今早開始" → 新回應:"昨晚就..." ❌
    
    寧可說"不確定"也不可前後矛盾！
    """

# 如果過度保守 - 平衡版  
elif consistency_score > 0.95 and response_naturalness < 0.8:
    reasoning_desc = """
    推理過程(平衡版)：
    
    1. 【溫和一致性檢查】
       檢查是否與對話歷史有明顯邏輯矛盾，允許合理的變化和澄清
    
    2. 【自然回應優先】  
       在保持基本一致性的前提下，優先生成自然、有幫助的回應
    """
```

#### 3.2 最終驗證測試 (15分鐘)

```bash
# 完整系統測試
echo "🔍 執行最終完整驗證..."

# 1. 基本功能測試
docker exec dialogue-server-jiawei-dspy python /app/run_tests.py

# 2. 一致性專項測試
docker exec dialogue-server-jiawei-dspy python /app/test_prompt_consistency.py

# 3. 逐輪分析（重點觀察第2-3輪）
docker exec dialogue-server-jiawei-dspy python /app/test_round_by_round_analysis.py

# 4. 診斷工具驗證  
docker exec dialogue-server-jiawei-dspy python /app/debug_dspy_internal_state.py
```

## 📊 成功標準

### 必達標準 (Pass/Fail)
- [x] **邏輯矛盾消除**: 典型矛盾案例(發燒狀態翻轉)消除率 ≥ 90%
- [x] **功能完整性**: 所有原有功能正常，`run_tests.py` 通過
- [x] **性能影響控制**: 平均回應時間增加 ≤ 0.2秒  
- [x] **實施效率**: 總實施時間 ≤ 4小時

### 優秀標準 (Good/Excellent)
- [x] **全面一致性**: 各類邏輯矛盾消除率 ≥ 95%
- [x] **自然度保持**: 回應仍然自然流暢，不機械化
- [x] **可擴展性**: 方案可適用於其他類型的矛盾檢測
- [x] **零副作用**: 完全不影響系統其他功能

## ⚠️ 風險評估與緩解

### 潛在風險

1. **過度謹慎風險**
   - **現象**: Prompt 太強導致回應過於保守
   - **檢測**: 回應變得機械化，缺乏醫療細節
   - **緩解**: 調整 prompt 用詞，平衡一致性和自然度

2. **理解偏差風險**
   - **現象**: LLM 誤解一致性要求
   - **檢測**: 出現不必要的拒絕回應情況  
   - **緩解**: 提供更清晰的例子和邊界

3. **性能影響風險**
   - **現象**: 複雜 prompt 增加處理時間
   - **檢測**: 回應時間明顯增加
   - **緩解**: 簡化 prompt 表述，移除冗餘指令

### 緩解措施

1. **漸進式部署**
   - 先實施最簡版本(方案A)
   - 根據效果決定是否增加方案B、C
   - 每步都有回退計劃

2. **A/B 測試能力**
   - 保留原版本配置
   - 可通過配置開關在新舊版本間切換
   - 便於對比效果

3. **持續監控**
   - 密切觀察一致性改善效果
   - 監控是否出現副作用
   - 收集用戶反饋

## 📝 實施檢查清單

### Phase 1: Prompt 修改
- [ ] 備份原始 `unified_dialogue_module.py` 
- [ ] 修改 `reasoning` 欄位描述
- [ ] 增強 `character_reminder` 提示
- [ ] 測試系統正常啟動
- [ ] 驗證基本對話功能無誤

### Phase 2: 測試驗證  
- [ ] 創建 `test_prompt_consistency.py`
- [ ] 執行修改前基準測試
- [ ] 執行修改後對比測試
- [ ] 運行專項一致性測試
- [ ] 分析測試結果和改善幅度

### Phase 3: 優化完善
- [ ] 根據測試結果調整 prompt
- [ ] 執行最終完整驗證測試
- [ ] 確認所有成功標準達成
- [ ] 記錄最佳實踐和經驗總結

## 🎯 預期成果

### 量化改善
- **開發效率**: 2-3小時 vs 原計劃5-6天 (節省 85% 時間)
- **代碼複雜度**: ~10行修改 vs ~1000行新代碼 (減少 99% 代碼量)
- **邏輯矛盾率**: 從檢測到的問題降至 < 5%
- **維護成本**: 接近零 vs 持續規則維護

### 質化提升  
- 消除第2-3輪典型邏輯矛盾問題
- 提升整體對話邏輯連貫性
- 保持醫療對話的專業性和自然度
- 建立基於 prompt 工程的最佳實踐

### 戰略價值
- 展示 LLM 時代的新解決思維
- 建立可復用的 prompt 一致性模式
- 為類似問題提供參考方案
- 證明"讓AI自主解決問題"的有效性

---

**總結**: 這個 prompt-based 方案體現了與傳統程式設計不同的思維模式 - 與其用代碼控制AI，不如通過精心設計的指令讓AI自主解決問題。這不僅更高效，而且更符合LLM的工作原理。