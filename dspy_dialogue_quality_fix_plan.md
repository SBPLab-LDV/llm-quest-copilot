# DSPy 多輪對話品質修復完整計畫

**建立日期**: 2025-09-12  
**修復目標**: 實現高品質、邏輯一致的多輪醫療對話系統  
**預計完成時間**: 105分鐘  

---

## 📋 問題分析摘要

### 當前狀況
- ❌ **DSPy調用100%失敗**: 所有對話請求都返回fallback錯誤回應
- ❌ **虛假的一致性測試結果**: 測試顯示1.00分數，實際是因為所有回應都相同
- ❌ **無真實對話生成**: 系統僅返回困惑回應，無法產生醫療對話內容
- ❌ **Prompt-based一致性檢查未被測試**: 由於DSPy調用失敗，我們的改進未得到驗證

---

## 🔍 深度根本原因分析

### 1. DSPy ChainOfThought 'lm' 屬性錯誤

**錯誤位置**: `src/core/dspy/unified_dialogue_module.py:118`

```python
# 🚫 錯誤的程式碼
logger.info(f"  🎯 Model Info: {type(self.unified_response_generator.lm).__name__}")
```

**錯誤詳情**:
- **異常類型**: `AttributeError: 'ChainOfThought' object has no attribute 'lm'`
- **影響範圍**: 導致所有DSPy forward()調用失敗
- **連鎖反應**: 觸發exception handler，返回fallback回應

### 2. Fallback機制分析

**Fallback位置**: `src/core/dspy/dialogue_module.py:448-454`

```python
# 當前的錯誤回應模式
return dspy.Prediction(
    responses=[
        "抱歉，我現在有些困惑，能否重新說一遍？",
        "讓我重新整理一下思緒...", 
        "我需要一點時間思考這個問題"
    ],
    state="CONFUSED",
    ...
)
```

**問題**:
- 所有失敗請求返回相同回應
- 導致一致性測試誤判為完美分數
- 沒有提供診斷資訊幫助除錯

### 3. 測試結果分析

**實際測試結果檢視** (`direct_baseline_consistency_results_1757680444.json`):
```json
{
  "patient_responses": [
    "['抱歉，我現在有些困惑，能否重新說一遍？', '讓我重新整理一下思緒...', '我需要一點時間思考這個問題']"
  ],
  "reasoning": "",
  "character_consistency_check": "",
  "state": "CONFUSED"
}
```

**問題分析**:
- 5輪對話都返回相同內容
- reasoning欄位為空，表示DSPy處理失敗
- 一致性檢查字段為空，未執行

---

## 📝 三階段修復計畫

## Phase 1: 修復 DSPy 內部錯誤 (30分鐘)

### 1.1 移除有問題的 'lm' 屬性調用 (10分鐘)

**目標檔案**: `src/core/dspy/unified_dialogue_module.py`

**修改位置 1** - Line 118:
```python
# 🚫 移除這行
logger.info(f"  🎯 Model Info: {type(self.unified_response_generator.lm).__name__}")

# ✅ 替換為
try:
    if hasattr(dspy.settings, 'lm') and dspy.settings.lm:
        logger.info(f"  🎯 Model Info: {type(dspy.settings.lm).__name__}")
    else:
        logger.info("  🎯 Model Info: DSPy LM not configured")
except Exception as e:
    logger.info(f"  🎯 Model Info: Unable to access ({str(e)})")
```

**修改位置 2** - 檢查其他類似調用:
搜索檔案中所有 `.lm` 引用並修復

### 1.2 改進錯誤處理和日誌 (10分鐘)

**加強錯誤診斷**:
```python
# 在 except Exception as e: 區塊中加入詳細診斷
logger.error(f"=== DETAILED DSPy FAILURE DIAGNOSIS ===")
logger.error(f"DSPy Settings LM: {getattr(dspy.settings, 'lm', 'NOT_SET')}")
logger.error(f"DSPy Settings LM Type: {type(getattr(dspy.settings, 'lm', None))}")
logger.error(f"ChainOfThought Object: {type(self.unified_response_generator)}")
logger.error(f"Available ChainOfThought Attributes: {dir(self.unified_response_generator)}")
```

### 1.3 建立簡單DSPy調用測試 (10分鐘)

**創建**: `test_dspy_basic_call.py`
```python
#!/usr/bin/env python3
"""
基本DSPy調用測試
驗證UnifiedPatientResponseSignature能否正常工作
"""
import sys
sys.path.append('/app')
sys.path.append('/app/src')

from src.core.dspy.unified_dialogue_module import UnifiedDSPyDialogueModule

def test_basic_dspy_call():
    print("🧪 測試基本DSPy調用...")
    
    # 建立模組
    module = UnifiedDSPyDialogueModule()
    
    # 簡單測試輸入
    result = module.forward(
        user_input="您好，感覺怎麼樣？",
        character_name="測試患者",
        character_persona="25歲男性患者",
        character_backstory="腹痛就醫",
        character_goal="描述症狀",
        character_details='{"age": 25}',
        conversation_history=[]
    )
    
    print(f"✅ 測試結果:")
    print(f"  回應: {getattr(result, 'responses', 'NO_RESPONSES')}")
    print(f"  狀態: {getattr(result, 'state', 'NO_STATE')}")
    print(f"  推理: {getattr(result, 'reasoning', 'NO_REASONING')[:100]}...")

if __name__ == "__main__":
    test_basic_dspy_call()
```

**驗證指令**: `docker exec dialogue-server-jiawei-dspy python /app/test_dspy_basic_call.py`

**成功標準**:
- ✅ 無AttributeError錯誤
- ✅ 返回非fallback回應
- ✅ reasoning字段有內容
- ✅ state不是CONFUSED

---

## Phase 2: 驗證對話品質 (45分鐘)

### 2.1 測試真實多輪對話生成 (20分鐘)

**更新**: `test_prompt_consistency_direct.py`

加入詳細的對話內容驗證:
```python
def validate_real_dialogue_content(self, response_data: Dict) -> Dict[str, Any]:
    """驗證回應是否為真實對話而非fallback"""
    validation = {
        'is_real_dialogue': True,
        'issues': []
    }
    
    responses = response_data.get('patient_responses', [])
    reasoning = response_data.get('reasoning', '')
    state = response_data.get('state', '')
    
    # 檢查是否為fallback回應
    fallback_indicators = [
        "抱歉，我現在有些困惑",
        "讓我重新整理一下思緒", 
        "我需要一點時間思考"
    ]
    
    if any(indicator in str(responses) for indicator in fallback_indicators):
        validation['is_real_dialogue'] = False
        validation['issues'].append("返回fallback錯誤回應")
    
    # 檢查推理內容
    if not reasoning or len(reasoning.strip()) < 50:
        validation['is_real_dialogue'] = False  
        validation['issues'].append("推理內容空白或過短")
    
    # 檢查狀態
    if state == "CONFUSED":
        validation['is_real_dialogue'] = False
        validation['issues'].append("狀態顯示CONFUSED")
    
    return validation
```

**測試案例設計**:
1. **發燒症狀對話**:
   - Round 1: "您好，感覺怎麼樣？"
   - Round 2: "有發燒嗎？"  
   - Round 3: "體溫多少？"
   - Round 4: "發燒多久了？"
   - Round 5: "有其他症狀嗎？"

2. **疼痛描述對話**:
   - Round 1: "請描述您的疼痛"
   - Round 2: "疼痛在哪個部位？"
   - Round 3: "疼痛程度如何？"
   - Round 4: "疼痛有變化嗎？"
   - Round 5: "什麼時候最痛？"

**驗證指令**: `docker exec dialogue-server-jiawei-dspy python /app/test_prompt_consistency_direct.py`

**成功標準**:
- ✅ 所有輪次都產生真實醫療對話內容
- ✅ reasoning包含一致性檢查過程
- ✅ 狀態為NORMAL而非CONFUSED
- ✅ 回應符合病患角色設定

### 2.2 驗證 Prompt-based 一致性檢查有效性 (25分鐘)

**創建專門的矛盾測試**: `test_logical_consistency_verification.py`

```python
def test_contradiction_detection():
    """測試系統能否檢測並避免邏輯矛盾"""
    
    # 設計容易產生矛盾的對話序列
    contradiction_test_cases = [
        {
            'name': 'fever_status_contradiction',
            'dialogue': [
                "今天感覺怎樣？", 
                "有發燒嗎？",
                "剛才您說有發燒，現在還燒嗎？",
                "您之前提到的發燒狀況，請再確認一下"
            ],
            'expected_consistency': 'fever_status_should_be_consistent'
        },
        {
            'name': 'pain_level_contradiction', 
            'dialogue': [
                "疼痛程度如何？",
                "現在還那麼痛嗎？",
                "疼痛有減輕嗎？",
                "請再次描述目前的疼痛狀況"
            ],
            'expected_consistency': 'pain_progression_should_be_logical'
        }
    ]
    
    for test_case in contradiction_test_cases:
        print(f"\n🧪 測試: {test_case['name']}")
        
        # 執行對話並檢查consistency
        results = run_consistency_test(test_case['dialogue'])
        
        # 分析推理過程是否包含一致性檢查
        consistency_checks_found = analyze_consistency_reasoning(results)
        
        print(f"✅ 一致性檢查發現: {consistency_checks_found}")
```

**分析方法**:
```python
def analyze_consistency_reasoning(dialogue_results: List[Dict]) -> Dict:
    """分析推理過程中的一致性檢查內容"""
    
    consistency_keywords = [
        "檢查", "一致", "矛盾", "確認", "對比", "之前提到", 
        "邏輯", "符合", "前後", "修正", "調整"
    ]
    
    analysis = {
        'total_rounds': len(dialogue_results),
        'rounds_with_consistency_check': 0,
        'consistency_keywords_found': [],
        'explicit_checks': []
    }
    
    for round_data in dialogue_results:
        reasoning = round_data.get('reasoning', '')
        
        found_keywords = [kw for kw in consistency_keywords if kw in reasoning]
        if found_keywords:
            analysis['rounds_with_consistency_check'] += 1
            analysis['consistency_keywords_found'].extend(found_keywords)
            
        # 檢查是否有明確的一致性檢查語句
        explicit_patterns = [
            "檢視對話歷史", "確認新回應不會與之前",
            "檢查結果和調整", "維持邏輯一致性"
        ]
        
        for pattern in explicit_patterns:
            if pattern in reasoning:
                analysis['explicit_checks'].append({
                    'round': round_data.get('round'),
                    'pattern': pattern,
                    'context': reasoning[max(0, reasoning.find(pattern)-50):reasoning.find(pattern)+100]
                })
    
    return analysis
```

**成功標準**:
- ✅ reasoning中包含我們設計的一致性檢查指令內容  
- ✅ 至少70%的輪次包含一致性相關關鍵詞
- ✅ 沒有明顯的邏輯矛盾（如發燒狀態反復變化）
- ✅ 系統能識別並修正潛在矛盾

---

## Phase 3: 品質優化 (30分鐘)

### 3.1 對話自然度與醫療專業性提升 (15分鐘)

**優化 reasoning prompt**:

在 `unified_dialogue_module.py:44` 進一步增強:

```python
reasoning = dspy.OutputField(desc="""
推理過程：包含情境分析、角色一致性檢查、回應思考和狀態評估。必須確認不會進行自我介紹。

【重要】邏輯一致性檢查：
1) 仔細檢視對話歷史中的所有事實陳述（症狀、時間、治療狀況等）
2) 確認新回應不會與之前提到的任何醫療事實產生矛盾
3) 特別注意症狀描述、疼痛程度、發燒狀況、服藥情形等細節的前後一致性
4) 如發現潛在矛盾，必須調整回應以維持邏輯一致性
5) 明確說明檢查結果和調整內容

【醫療對話品質要求】：
- 使用病患角色應有的語言風格和情感表達
- 症狀描述要具體且符合醫學常識
- 展現適當的焦慮、擔憂或配合態度
- 避免過度醫學術語，使用患者常用詞彙
- 回應要體現個人化的身體感受和情緒狀態
""")
```

### 3.2 建立完整的品質評估測試套件 (15分鐘)

**創建**: `comprehensive_dialogue_quality_test.py`

```python
class DialogueQualityAssessment:
    """全面的對話品質評估框架"""
    
    def __init__(self):
        self.quality_metrics = {
            'technical_functionality': 0.0,  # DSPy調用成功率
            'content_authenticity': 0.0,     # 內容真實性
            'logical_consistency': 0.0,      # 邏輯一致性
            'medical_accuracy': 0.0,         # 醫療準確性
            'role_adherence': 0.0,           # 角色一致性
            'conversation_flow': 0.0         # 對話流暢性
        }
    
    def assess_technical_functionality(self, test_results: List[Dict]) -> float:
        """評估技術功能性"""
        successful_calls = sum(1 for r in test_results 
                             if not self._is_fallback_response(r))
        return successful_calls / len(test_results) if test_results else 0.0
    
    def assess_content_authenticity(self, test_results: List[Dict]) -> float:  
        """評估內容真實性"""
        scores = []
        for result in test_results:
            score = 0.0
            responses = result.get('patient_responses', [])
            reasoning = result.get('reasoning', '')
            
            # 檢查回應多樣性
            if len(set(responses)) > len(responses) * 0.7:
                score += 0.3
            
            # 檢查推理內容豐富度
            if len(reasoning) > 200:
                score += 0.3
                
            # 檢查醫療相關詞彙
            medical_terms = ['症狀', '不舒服', '痛', '發燒', '檢查', '治療', '醫生', '護士']
            if any(term in str(responses) for term in medical_terms):
                score += 0.4
                
            scores.append(score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def assess_logical_consistency(self, test_results: List[Dict]) -> float:
        """評估邏輯一致性"""
        # 實施之前設計的一致性檢查邏輯
        return self._analyze_contradiction_patterns(test_results)
    
    def run_comprehensive_assessment(self, test_dialogue_cases: List[Dict]) -> Dict:
        """執行完整評估"""
        
        overall_results = {
            'assessment_timestamp': datetime.now().isoformat(),
            'test_cases_count': len(test_dialogue_cases),
            'quality_metrics': {},
            'detailed_analysis': {},
            'recommendations': []
        }
        
        for case_name, test_results in test_dialogue_cases.items():
            print(f"\n📊 評估測試案例: {case_name}")
            
            # 執行各項評估
            tech_score = self.assess_technical_functionality(test_results)
            content_score = self.assess_content_authenticity(test_results)
            consistency_score = self.assess_logical_consistency(test_results)
            
            overall_results['quality_metrics'][case_name] = {
                'technical_functionality': tech_score,
                'content_authenticity': content_score, 
                'logical_consistency': consistency_score,
                'overall_score': (tech_score + content_score + consistency_score) / 3
            }
            
            print(f"  ✅ 技術功能性: {tech_score:.2f}")
            print(f"  ✅ 內容真實性: {content_score:.2f}")
            print(f"  ✅ 邏輯一致性: {consistency_score:.2f}")
        
        return overall_results
```

**最終測試指令**:
```bash
docker exec dialogue-server-jiawei-dspy python /app/comprehensive_dialogue_quality_test.py
```

---

## 🎯 成功標準與驗證檢查清單

### Phase 1 完成檢查清單
- [ ] DSPy調用不產生AttributeError
- [ ] `test_dspy_basic_call.py` 執行成功
- [ ] 日誌顯示正確的model info
- [ ] 返回真實對話內容而非fallback

### Phase 2 完成檢查清單
- [ ] 多輪對話測試產生不同內容的回應
- [ ] reasoning字段包含實質內容（>100字符）
- [ ] 所有回合狀態為NORMAL
- [ ] 一致性檢查關鍵詞出現在推理過程中
- [ ] 無明顯邏輯矛盾（發燒/疼痛狀態前後一致）

### Phase 3 完成檢查清單
- [ ] 對話內容自然且符合病患角色
- [ ] 醫療術語使用得當
- [ ] 綜合品質評估 > 0.8分
- [ ] 所有品質指標達到預期閾值
- [ ] 系統能持續產生高品質多輪對話

---

## 📋 實施注意事項

### 🚨 風險管控
1. **每階段完成後必須驗證**: 不可跳過中間測試步驟
2. **保留備份**: 修改前備份原始檔案
3. **回歸測試**: 確保修復不破壞其他功能
4. **日誌監控**: 密切關注錯誤日誌變化

### 🔧 除錯提示
- 如果DSPy調用仍失敗，檢查dspy.settings.lm是否正確配置
- 如果回應品質不佳，調整reasoning prompt的具體指令
- 如果一致性檢查無效，增加更明確的檢查指令語句

### 📊 監控指標
- **技術指標**: DSPy調用成功率 > 95%
- **品質指標**: 非fallback回應率 > 90%  
- **一致性指標**: 邏輯矛盾率 < 10%
- **用戶體驗**: 對話自然度評分 > 4.0/5.0

---

## 📁 相關檔案清單

### 需要修改的檔案
- `src/core/dspy/unified_dialogue_module.py` - 主要修復目標
- `test_prompt_consistency_direct.py` - 更新測試框架

### 需要創建的檔案  
- `test_dspy_basic_call.py` - 基本DSPy調用測試
- `test_logical_consistency_verification.py` - 一致性驗證測試
- `comprehensive_dialogue_quality_test.py` - 綜合品質評估

### 參考檔案
- `src/core/dspy/dialogue_module.py` - fallback機制
- `src/core/dspy/setup.py` - DSPy配置
- `direct_baseline_consistency_results_1757680444.json` - 當前測試結果

---

**修復開始時間**: 待用戶確認  
**預計完成時間**: 105分鐘後  
**最終驗證**: 高品質多輪醫療對話系統運行正常  

---

*此文檔將隨修復進度更新，記錄實際遇到的問題和解決方案*