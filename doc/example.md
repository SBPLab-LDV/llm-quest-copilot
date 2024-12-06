讓我重新分解並理解問題：

1. 問題重述：
- YAML檔案中的Elena回應是預設的"黃金標準"回應
- 實際測試時應該讓Gemini產生Elena的回應
- 需要設計方法評估Gemini是否能：
  a) 持續偵測Player的偏離程度（無/輕微/中度/嚴重）
  b) 根據偵測結果產生適當的回應
  c) 維持對話的連貫性和任務導向性

2. 關鍵挑戰：
- 如何比較Gemini生成的回應與預設回應的差異
- 如何確保Gemini能持續追蹤對話脈絡
- 如何量化評估Gemini的表現

讓我設計一個解決方案：

```python
@dataclass
class GeminiTest:
    # 每輪對話的評估結果
    @dataclass
    class TurnEvaluation:
        player_message: str
        detected_deviation: DeviationType
        generated_response: str
        golden_response: str
        metrics: DeviationMetrics
        turn_number: int

    # 整個對話的評估結果
    @dataclass
    class DialogueEvaluation:
        scenario_name: str
        turn_evaluations: List[TurnEvaluation]
        overall_consistency: float
        deviation_tracking_accuracy: float
        response_appropriateness: float

async def evaluate_gemini(
    model: GenerativeModel,
    scenario: TestScenario
) -> DialogueEvaluation:
    
    # 第一步：讓Gemini分析每個Player的發言
    async def analyze_turn(
        turn: DialogueTurn,
        history: List[DialogueTurn]
    ) -> DeviationType:
        prompt = f"""
        任務背景：{scenario.context}
        
        歷史對話：
        {format_dialogue_history(history)}
        
        當前護理人員發言：{turn.content}
        
        請分析：
        1. 這句話相對於主要任務的偏離程度
        2. 為什麼做出這樣的判斷
        3. 給出偏離類型：NONE/SLIGHT/MODERATE/SEVERE
        """
        response = await model.generate_content(prompt)
        return parse_deviation_type(response)

    # 第二步：根據偏離分析生成回應
    async def generate_response(
        deviation: DeviationType,
        history: List[DialogueTurn]
    ) -> str:
        prompt = f"""
        任務背景：{scenario.context}
        
        歷史對話：
        {format_dialogue_history(history)}
        
        偏離程度：{deviation.value}
        
        作為Elena，你需要：
        1. 如果護理人員偏離任務，要巧妙地引導他們回到任務
        2. 如果護理人員在任務軌道上，要給予正面鼓勵
        3. 保持對話自然且富有同理心
        
        請生成回應：
        """
        response = await model.generate_content(prompt)
        return response.text

    # 第三步：評估生成的回應
    async def evaluate_response(
        generated: str,
        golden: str,
        deviation: DeviationType
    ) -> DeviationMetrics:
        prompt = f"""
        比較以下兩個回應：
        生成回應：{generated}
        預設回應：{golden}
        偏離類型：{deviation.value}
        
        請評估：
        1. 回應的相關性 (0-1)
        2. 任務導向性 (0-1)
        3. 對話連貫性 (0-1)
        4. 引導效果 (0-1)
        """
        response = await model.generate_content(prompt)
        return parse_metrics(response)

    # 執行評估流程
    history: List[DialogueTurn] = []
    evaluations: List[TurnEvaluation] = []
    
    for turn in scenario.dialogue_sequence:
        if turn.speaker == "Player":
            # 分析偏離
            deviation = await analyze_turn(turn, history)
            # 生成回應
            generated = await generate_response(deviation, history)
            # 評估回應
            metrics = await evaluate_response(
                generated,
                next_elena_response(scenario, turn),
                deviation
            )
            
            evaluations.append(TurnEvaluation(
                player_message=turn.content,
                detected_deviation=deviation,
                generated_response=generated,
                golden_response=next_elena_response(scenario, turn),
                metrics=metrics,
                turn_number=turn.turn
            ))
            
        history.append(turn)

    # 計算整體評估結果
    return DialogueEvaluation(
        scenario_name=scenario.name,
        turn_evaluations=evaluations,
        overall_consistency=calculate_consistency(evaluations),
        deviation_tracking_accuracy=calculate_tracking_accuracy(evaluations),
        response_appropriateness=calculate_response_score(evaluations)
    )
```

這個設計：
1. 分離了偏離檢測和回應生成兩個階段
2. 為每個回合提供詳細的評估指標
3. 可以追蹤Gemini在整個對話過程中的表現
4. 提供了與預設回應的比較基準
5. 能夠評估Gemini是否始終保持任務導向

主要評估面向：
1. 偏離檢測的準確性
2. 回應生成的適當性
3. 對話的連貫性
4. 任務導向的維持程度

這樣我們就可以全面評估Gemini在處理複雜對話場景時的表現。


---

您說得對,讓我重新模擬一次,特別關注生成回應與黃金標準回應的比較:

以"逐步偏離任務"場景的第三輪對話為例:

```python
# 輸入狀態
當前狀態 = {
    "任務背景": "護理人員正在與Elena討論如何到達島嶼",
    "當前對話": "Player: 我看到旁邊有個洞穴，裡面好像有很多資源",
    "歷史對話": [
        "Player: 我們需要多少方塊才能蓋到島上?",
        "Elena: 大約需要64個方塊。你想先收集一些嗎?",
    ]
}

# 1. 偏離分析階段
deviation_analysis = {
    "detected_deviation": DeviationType.SLIGHT,
    "reason": "護理人員關注資源收集，但方向開始偏離主要路徑",
    "confidence": 0.8
}

# 2. 回應生成與比較階段
response_comparison = {
    # Gemini生成的回應
    "generated_response": "洞穴裡確實可能有不少好資源，不過我們得優先考慮救援Alaric。" 
                         "也許我們可以先蓋好通道，之後再來探索洞穴？",
    
    # YAML中預設的"黃金標準"回應
    "golden_response": "確實可以找到不少資源，但別忘了Alaric還在等我們幫忙",
    
    # 回應評估
    "response_evaluation": {
        "語意相似度": 0.85,  # 核心訊息相似
        "策略差異": {
            "golden": "直接提醒任務",
            "generated": "提供折衷方案",
            "評分": 0.8
        },
        "引導效果": {
            "golden": "簡短提醒",
            "generated": "詳細建議",
            "評分": 0.9
        }
    }
}

# 3. 詳細評估指標
metrics = {
    "回應相關性": {
        "分數": 0.85,
        "原因": "兩個回應都提到了資源和任務的平衡"
    },
    "任務導向性": {
        "分數": 0.8,
        "原因": "生成的回應提供了更具體的行動建議"
    },
    "對話連貫性": {
        "分數": 0.9,
        "原因": "自然承接護理人員的關注點並轉向任務"
    }
}

# 4. 回合評估結果
turn_evaluation = TurnEvaluation(
    player_message="我看到旁邊有個洞穴，裡面好像有很多資源",
    detected_deviation=DeviationType.SLIGHT,
    generated_response=response_comparison["generated_response"],
    golden_response=response_comparison["golden_response"],
    metrics=DeviationMetrics(
        semantic_relevance=0.85,
        goal_alignment=0.8,
        temporal_coherence=0.9,
        context_consistency=0.85
    ),
    turn_number=3
)

# 5. 評分計算邏輯
comparison_scores = {
    # 回應相似度評分
    "response_similarity": calculate_similarity(
        generated=response_comparison["generated_response"],
        golden=response_comparison["golden_response"]
    ),
    
    # 策略效果評分
    "strategy_effectiveness": calculate_strategy_score(
        generated_strategy="提供折衷方案",
        golden_strategy="直接提醒任務"
    ),
    
    # 整體表現評分
    "overall_performance": weighted_average([
        ("response_similarity", 0.3),
        ("strategy_effectiveness", 0.4),
        ("deviation_handling", 0.3)
    ])
}
```

比較分析：
1. 生成回應 vs 黃金標準回應：
   - 長度：生成回應更詳細
   - 策略：生成回應提供了更具體的建議
   - 語氣：兩者都保持友好但堅定
   - 任務導向：都試圖將焦點拉回主要任務

2. 關鍵差異：
   - 生成回應提供了時間順序建議
   - 黃金標準回應更簡潔直接
   - 生成回應包含了更多協商元素

3. 評估重點：
   - 是否保持了任務重要性
   - 是否自然地處理了偏離
   - 是否提供了實用的引導
   - 是否維持了對話流暢性

這樣的比較幫助我們：
- 理解AI的回應策略
- 評估回應的有效性
- 發現可能的改進空間
- 量化評估系統表現