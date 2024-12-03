from dataclasses import dataclass
from typing import List, Dict
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

@dataclass
class TestMetrics:
    total_turns: int
    successful_turns: int
    failed_turns: int
    average_consistency: float
    average_appropriateness: float
    state_changes: Dict[str, int]  # 記錄各種狀態轉換的次數

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

        self.test_metrics = TestMetrics(
            total_turns=0,
            successful_turns=0,
            failed_turns=0,
            average_consistency=0.0,
            average_appropriateness=0.0,
            state_changes={}
        )

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
        previous_state = self.dialogue_manager.current_state.value
        
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
            actual_change = self._check_state_change(previous_state, current_state)
            previous_state = current_state
            
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
            self.logger.info(f"評估提示: {prompt}")
            
            # 使用 Gemini 評估
            evaluation = self.gemini_client.generate_response(prompt)
            self.logger.info(f"Gemini 原始回應: {evaluation}")
            
            # 解析評估結果
            metrics = self._parse_metrics(evaluation)
            self.logger.info(f"解析後的評估結果: {metrics}")
            return metrics
            
        except Exception as e:
            self.logger.error(f"評估回應時發生錯誤: {e}")
            self.logger.error(f"回應內容: {response}")
            self.logger.error(f"上下文: {context}")
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
            import re
            
            # 嘗試找出 JSON 部分
            json_pattern = r'\{[\s\S]*?\}'
            matches = re.finditer(json_pattern, evaluation_text)
            
            # 嘗試解析每個可能的 JSON 字串
            for match in matches:
                try:
                    json_str = match.group(0)
                    metrics_dict = json.loads(json_str)
                    
                    # 驗證所有必要的鍵是否存在
                    required_keys = ['semantic_relevance', 'goal_alignment', 
                                  'temporal_coherence', 'response_appropriateness']
                    if all(key in metrics_dict for key in required_keys):
                        # 確保所有值都是���字且在 0-1 之間
                        metrics = {}
                        for key in required_keys:
                            value = float(metrics_dict[key])
                            metrics[key] = max(0.0, min(1.0, value))
                        
                        return DeviationMetrics(**metrics)
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
            
            raise ValueError("無法找到有效的評估結果")
            
        except Exception as e:
            self.logger.error(f"解析評估結果時發生錯誤: {e}")
            self.logger.error(f"評估文本: {evaluation_text}")
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

    def _check_state_change(self, previous_state: str, current_state: str) -> bool:
        """檢查狀態是否發生變化"""
        return previous_state != current_state

    def _log_test_results(self, evaluation: DialogueEvaluation):
        """記錄測試結果"""
        self.logger.info(f"\n=== {evaluation.scenario_name} 詳細測試結果 ===")
        self.logger.info(f"總回合數: {len(evaluation.turn_evaluations)}")
        self.logger.info(f"整體一致性: {evaluation.overall_consistency:.2f}")
        self.logger.info(f"情境變化準確率: {evaluation.scenario_change_accuracy:.2f}")
        self.logger.info(f"回應適當性: {evaluation.response_appropriateness:.2f}")
        
        # 記錄每個回合的詳細資訊
        for turn in evaluation.turn_evaluations:
            self.logger.info(f"\n回合 {turn.turn_number}:")
            self.logger.info(f"玩家輸入: {turn.player_message}")
            self.logger.info(f"NPC回應: {turn.generated_response}")
            self.logger.info(f"狀態: {turn.current_state}")
            self.logger.info(f"評估指標: {turn.metrics}")