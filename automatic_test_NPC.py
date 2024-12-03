import asyncio
import yaml
import re
import os
from dataclasses import dataclass
from typing import List
from NPC import DialogueManager, Character, DialogueState
import google.generativeai as genai  # 直接導入 genai

# 讀取設定檔
try:
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
        GOOGLE_API_KEY = config.get('google_api_key')
except FileNotFoundError:
    # 如果找不到設定檔，嘗試從環境變數讀取
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    if not GOOGLE_API_KEY:
        raise ValueError("找不到 Google API Key，請在 config.yaml 設定或設定環境變數 GOOGLE_API_KEY")

# 設定 Gemini
genai.configure(api_key=GOOGLE_API_KEY)
# 初始化 Gemini 模型
model = genai.GenerativeModel('gemini-1.5-flash')
@dataclass
class DeviationMetrics:
    semantic_relevance: float
    goal_alignment: float
    temporal_coherence: float
    response_appropriateness: float

@dataclass
class TurnEvaluation:
    player_message: str
    generated_response: str
    expected_scenario_change: bool
    actual_scenario_change: bool
    current_state: str
    metrics: DeviationMetrics
    turn_number: int

@dataclass
class DialogueEvaluation:
    scenario_name: str
    turn_evaluations: List[TurnEvaluation]
    overall_consistency: float
    scenario_change_accuracy: float
    response_appropriateness: float

class NPCScenarioTester:
    def __init__(self, dialogue_manager):
        self.dialogue_manager = dialogue_manager
        self.total_score = 0
        self.total_interactions = 0
        self.test_results = []
        # 讀取提示詞
        try:
            with open('prompts.yaml', 'r', encoding='utf-8') as file:
                self.prompts = yaml.safe_load(file)
        except FileNotFoundError:
            print("錯誤：找不到 prompts.yaml 檔案")
            raise
        except yaml.YAMLError as e:
            print(f"錯誤：YAML 檔案格式不正確: {e}")
            raise

    async def evaluate_response(self, response: str, context: dict) -> DeviationMetrics:
        """使用 Gemini 評估回應品質"""
        try:
            # 從 YAML 讀取提示詞模板並填入變數
            prompt = self.prompts['evaluation_prompt'].format(
                current_state=context['current_state'],
                player_input=context['player_input'],
                response=response
            )
        except KeyError as e:
            print(f"錯誤：提示詞模板中缺少必要的鍵值: {e}")
            raise
        except ValueError as e:
            print(f"錯誤：提示詞格式化失敗: {e}")
            raise
        
        # 使用 gemini 實例
        evaluation = model.generate_content(prompt)
        # 解析 Gemini 的評估結果
        metrics = self._parse_metrics(evaluation.text)
        return metrics

    def _parse_metrics(self, evaluation_text: str) -> DeviationMetrics:
        """解析 Gemini 回傳的 JSON 格式評估結果"""
        try:
            import json
            metrics_dict = json.loads(evaluation_text)
            return DeviationMetrics(
                semantic_relevance=float(metrics_dict['semantic_relevance']),
                goal_alignment=float(metrics_dict['goal_alignment']),
                temporal_coherence=float(metrics_dict['temporal_coherence']),
                response_appropriateness=float(metrics_dict['response_appropriateness'])
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"解析評估結果時發生錯誤: {e}")
            # 發生錯誤時返回預設值
            return DeviationMetrics(
                semantic_relevance=0.5,
                goal_alignment=0.5,
                temporal_coherence=0.5,
                response_appropriateness=0.5
            )

    async def _test_single_scenario(self, scenario) -> DialogueEvaluation:
        turn_evaluations = []
        scenario_score = 0
        
        for turn_num, interaction in enumerate(scenario['interactions'], 1):
            user_input = interaction['input']
            expected_change = interaction.get('scenario_changed', False)
            
            # 獲取 NPC 回應
            response = await self.dialogue_manager.process_turn(user_input)
            
            # 分析當前狀態
            state_match = re.search(r'當前對話狀態: (\w+)', response)
            current_state = state_match.group(1) if state_match else "UNKNOWN"
            actual_change = current_state == 'TRANSITIONING'
            
            # 評估回應
            context = {
                'current_state': current_state,
                'player_input': user_input
            }
            metrics = await self.evaluate_response(response, context)
            
            # 記錄評估結果
            turn_evaluations.append(TurnEvaluation(
                player_message=user_input,
                generated_response=response,
                expected_scenario_change=expected_change,
                actual_scenario_change=actual_change,
                current_state=current_state,
                metrics=metrics,
                turn_number=turn_num
            ))
            
            # 更新分數
            if actual_change == expected_change:
                scenario_score += 1
            
            # 輸出詳細資訊
            self._print_turn_evaluation(turn_evaluations[-1])

        return DialogueEvaluation(
            scenario_name=scenario['name'],
            turn_evaluations=turn_evaluations,
            overall_consistency=self._calculate_consistency(turn_evaluations),
            scenario_change_accuracy=scenario_score / len(scenario['interactions']),
            response_appropriateness=self._calculate_appropriateness(turn_evaluations)
        )

    def _print_turn_evaluation(self, eval: TurnEvaluation):
        print(f"\n=== 回合 {eval.turn_number} 評估 ===")
        print(f"玩家輸入: {eval.player_message}")
        print(f"NPC回應: {eval.generated_response}")
        print(f"預期情境變化: {eval.expected_scenario_change}")
        print(f"實際情境變化: {eval.actual_scenario_change}")
        print("\n品質評估:")
        print(f"- 語意相關性: {eval.metrics.semantic_relevance:.2f}")
        print(f"- 目標一致性: {eval.metrics.goal_alignment:.2f}")
        print(f"- 時序連貫性: {eval.metrics.temporal_coherence:.2f}")
        print(f"- 回應適當性: {eval.metrics.response_appropriateness:.2f}")

    def _calculate_consistency(self, evaluations: List[TurnEvaluation]) -> float:
        return sum(e.metrics.temporal_coherence for e in evaluations) / len(evaluations)

    def _calculate_appropriateness(self, evaluations: List[TurnEvaluation]) -> float:
        return sum(e.metrics.response_appropriateness for e in evaluations) / len(evaluations)

async def main():
    # 創建角色實例（保持不變）
    character = Character(
        name="Elena",
        persona="一位剛動完手術的口腔癌患者",
        backstory="手術動完之後常常講話別人聽不懂，但還是試圖與醫護人員闡述自己的描述",
        goal="希望能夠與醫護人員溝通，讓他們了解自己的狀況"
    )
    
    # 創建對話管理器
    manager = DialogueManager(character)
    
    # 讀取測試情境
    try:
        with open('test_scenarios.yaml', 'r', encoding='utf-8') as file:
            yaml_data = yaml.safe_load(file)
            test_scenarios = yaml_data['scenarios']
    except FileNotFoundError:
        print("錯誤：找不到 test_scenarios.yaml 檔案")
        return
    except yaml.YAMLError as e:
        print(f"錯誤：YAML 檔案格式不正確: {e}")
        return
    
    # 創建情境測試器（移除 model 參數）
    scenario_tester = NPCScenarioTester(manager)
    
    # 運行自動化測試
    for scenario in test_scenarios:
        evaluation = await scenario_tester._test_single_scenario(scenario)
        print(f"\n=== {scenario['name']} 測試結果 ===")
        print(f"整體一致性: {evaluation.overall_consistency:.2f}")
        print(f"情境變化準確率: {evaluation.scenario_change_accuracy:.2f}")
        print(f"回應適當性: {evaluation.response_appropriateness:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
