from dataclasses import dataclass
from typing import List
import re
import yaml
from pathlib import Path
from ..core.dialogue import DialogueManager
from ..llm.gemini_client import GeminiClient
from .test_scenarios.scenarios import load_test_scenarios
from ..utils.logger import setup_logger

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
    def __init__(self, dialogue_manager: DialogueManager):
        self.dialogue_manager = dialogue_manager
        self.total_score = 0
        self.total_interactions = 0
        self.test_results = []
        self.gemini_client = GeminiClient()
        self.logger = setup_logger('npc_tester')
        
        # 修改 prompts 路徑
        prompts_path = Path(__file__).parent.parent.parent / 'prompts' / 'dialogue_prompts.yaml'
        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)

    async def run_tests(self):
        """運行所有測試情境"""
        self.logger.info("開始執行自動化NPC情境測試")
        scenarios = load_test_scenarios()
        print("\n=== 自動化NPC情境測試 ===")
        
        for scenario in scenarios:
            evaluation = await self._test_single_scenario(scenario)
            print(f"\n=== {scenario['name']} 測試結果 ===")
            print(f"整體一致性: {evaluation.overall_consistency:.2f}")
            print(f"情境變化準確率: {evaluation.scenario_change_accuracy:.2f}")
            print(f"回應適當性: {evaluation.response_appropriateness:.2f}")
            

    async def _test_single_scenario(self, scenario) -> DialogueEvaluation:
        """測試單個情境"""
        turn_evaluations = []
        scenario_score = 0
        
        self.logger.info(f"\n[開始測試情境 {scenario['name']}]")
        
        for turn_num, interaction in enumerate(scenario['interactions'], 1):
            user_input = interaction['input']
            expected_change = interaction.get('scenario_changed', False)
            
            self.logger.info(f"\n--- 回合 {turn_num} ---")
            self.logger.info(f"玩家輸入: {user_input}")
            
            # 獲取 NPC 回應
            response = await self.dialogue_manager.process_turn(user_input)
            self.logger.info(f"NPC回應: {response}")
            
            # 分析當前狀態
            state_match = re.search(r'當前對話狀態: (\w+)', response)
            current_state = state_match.group(1) if state_match else "UNKNOWN"
            actual_change = current_state == 'TRANSITIONING'
            
            # 評估回應
            context = {
                'current_state': current_state,
                'player_input': user_input
            }
            metrics = await self._evaluate_response(response, context)
            self.logger.info(f"評估結果: {metrics}")
            
            # 記錄評估結果
            turn_eval = TurnEvaluation(
                player_message=user_input,
                generated_response=response,
                expected_scenario_change=expected_change,
                actual_scenario_change=actual_change,
                current_state=current_state,
                metrics=metrics,
                turn_number=turn_num
            )
            turn_evaluations.append(turn_eval)
            
            # 更新分數
            if actual_change == expected_change:
                scenario_score += 1
            
            self._print_turn_evaluation(turn_eval)

        # 計算整體評估結果
        evaluation = DialogueEvaluation(
            scenario_name=scenario['name'],
            turn_evaluations=turn_evaluations,
            overall_consistency=self._calculate_consistency(turn_evaluations),
            scenario_change_accuracy=scenario_score / len(scenario['interactions']),
            response_appropriateness=self._calculate_appropriateness(turn_evaluations)
        )
        
        self.logger.info(f"\n=== {scenario['name']} 測試結果 ===")
        self.logger.info(f"整體一致性: {evaluation.overall_consistency:.2f}")
        self.logger.info(f"情境變化準確率: {evaluation.scenario_change_accuracy:.2f}")
        self.logger.info(f"回應適當性: {evaluation.response_appropriateness:.2f}")
        
        return evaluation

    async def _evaluate_response(self, response: str, context: dict) -> DeviationMetrics:
        """評估回應品質"""
        try:
            # 從 YAML 讀取提示詞模板並填入變數
            prompt = self.prompts['evaluation_prompt'].format(
                current_state=context['current_state'],
                player_input=context['player_input'],
                response=response
            )
            print(f"\n評估提示: {prompt}")
            
            # 使用 Gemini 評估
            evaluation = self.gemini_client.generate_response(prompt)
            
            # 解析評估結果
            return self._parse_metrics(evaluation)
            
        except Exception as e:
            self.logger.error(f"評估回應時發生錯誤: {e}")
            self.logger.error(f"Gemini 回傳內容: {evaluation}")
            return DeviationMetrics(
                semantic_relevance=0.5,
                goal_alignment=0.5,
                temporal_coherence=0.5,
                response_appropriateness=0.5
            )

    def _parse_metrics(self, evaluation_text: str) -> DeviationMetrics:
        """解析評估結果"""
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
            return DeviationMetrics(
                semantic_relevance=0.5,
                goal_alignment=0.5,
                temporal_coherence=0.5,
                response_appropriateness=0.5
            )

    def _print_turn_evaluation(self, eval: TurnEvaluation):
        """輸出回合評估結果"""
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
        """計算整體一致性"""
        if not evaluations:
            return 0.0
        return sum(e.metrics.temporal_coherence for e in evaluations) / len(evaluations)

    def _calculate_appropriateness(self, evaluations: List[TurnEvaluation]) -> float:
        """計算整體適當性"""
        if not evaluations:
            return 0.0
        return sum(e.metrics.response_appropriateness for e in evaluations) / len(evaluations)