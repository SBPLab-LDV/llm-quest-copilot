"""
Scenario Manager - 管理 prompts/scenarios/ 下的情境 YAML 檔案

功能：
1. 載入所有 scenario YAML 檔案
2. 建立關鍵字索引，用於快速匹配
3. 提供 few-shot 範例給 LLM 使用
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

logger = logging.getLogger(__name__)


class ScenarioManager:
    """管理對話情境與 few-shot 範例載入"""

    # 情境名稱對應（中文 ↔ 現有英文 ID）
    CONTEXT_MAPPING = {
        "病房日常": "daily_routine_examples",
        "醫師查房": "doctor_visit_examples",
        "門診醫師問診": "outpatient_examples",
        "門診護理詢問": "outpatient_nursing_examples",
        "傷口管路相關": "wound_tube_care_examples",
        "生命徵象": "vital_signs_examples",
        "身體評估": "physical_assessment_examples",
        "治療相關給藥化放療手術": "treatment_examples",
        "營養諮詢": "nutrition_examples",
        "物理治療": "rehabilitation_examples",
        "檢查相關": "examination_examples",
        "個管師對話": "case_manager_examples",
        "照顧者互動": "caregiver_examples",
    }

    # 反向對應
    CONTEXT_MAPPING_REVERSE = {v: k for k, v in CONTEXT_MAPPING.items()}

    # 第一輪對話用的預設範例（確保多角色覆蓋，解決雞生蛋問題）
    BOOTSTRAP_EXAMPLES = [
        {
            "question": "嘴巴現在張得怎麼樣？有沒有比較打開？",
            "speakers": ["物理治療師"],
            "keywords": ["張口", "張嘴", "嘴巴"],
            "patient_responses": ["比較打開了", "還是有點緊", "比昨天好一點"]
        },
        {
            "question": "你現在有在補充什麼營養品嗎？",
            "speakers": ["營養師"],
            "keywords": ["營養品", "配方奶", "補充"],
            "patient_responses": ["我有在吃配方奶", "沒有特別補充", "有吃一些維他命"]
        },
        {
            "question": "你今天感覺怎麼樣？有沒有哪裡不舒服？",
            "speakers": ["護理師"],
            "keywords": ["感覺", "不舒服"],
            "patient_responses": ["還好", "有點累", "比昨天好"]
        },
        {
            "question": "傷口恢復得怎麼樣？",
            "speakers": ["醫師"],
            "keywords": ["傷口", "恢復", "檢查報告"],
            "patient_responses": ["還好，沒什麼感覺", "有點痛", "看起來在癒合"]
        },
        {
            "question": "爸，你今天有沒有比較好一點？",
            "speakers": ["照顧者"],
            "keywords": ["爸", "媽", "阿公", "阿嬤"],
            "patient_responses": ["有啦，今天好多了", "差不多", "比較有精神了"]
        },
    ]

    def __init__(self, scenarios_dir: str = None):
        """初始化 ScenarioManager

        Args:
            scenarios_dir: scenarios YAML 檔案所在目錄，預設為 prompts/scenarios
        """
        if scenarios_dir is None:
            # 找到專案根目錄
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            scenarios_dir = project_root / "prompts" / "scenarios"

        self.scenarios_dir = Path(scenarios_dir)
        self.scenarios: Dict[str, List[Dict[str, Any]]] = {}
        self.keyword_index: Dict[str, Set[str]] = {}
        self.speaker_index: Dict[str, Set[str]] = {}

        self._load_all_scenarios()
        self._build_keyword_index()
        self._build_speaker_index()

        logger.info(
            f"ScenarioManager 初始化完成: 載入 {len(self.scenarios)} 個情境, "
            f"{len(self.keyword_index)} 個關鍵字索引"
        )

    def _load_all_scenarios(self) -> None:
        """載入所有 scenario YAML 檔案"""
        if not self.scenarios_dir.exists():
            logger.warning(f"Scenarios 目錄不存在: {self.scenarios_dir}")
            return

        for yaml_file in self.scenarios_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                scenario_name = data.get("scenario", yaml_file.stem)
                questions = data.get("questions", [])

                self.scenarios[scenario_name] = questions
                logger.debug(
                    f"載入情境 '{scenario_name}': {len(questions)} 個問題"
                )

            except Exception as e:
                logger.error(f"載入 {yaml_file} 失敗: {e}")

    def _build_keyword_index(self) -> None:
        """建立關鍵字 -> 情境的索引"""
        for scenario_name, questions in self.scenarios.items():
            for q in questions:
                keywords = q.get("keywords", [])
                for kw in keywords:
                    if kw not in self.keyword_index:
                        self.keyword_index[kw] = set()
                    self.keyword_index[kw].add(scenario_name)

    def _build_speaker_index(self) -> None:
        """建立 speaker -> 情境的索引"""
        for scenario_name, questions in self.scenarios.items():
            for q in questions:
                speakers = q.get("speakers", [])
                for speaker in speakers:
                    if speaker not in self.speaker_index:
                        self.speaker_index[speaker] = set()
                    self.speaker_index[speaker].add(scenario_name)

    def find_by_keywords(self, user_input: str) -> List[str]:
        """根據使用者輸入的關鍵字找匹配的情境

        Args:
            user_input: 使用者輸入的問題

        Returns:
            匹配的情境名稱列表，按相關度排序
        """
        if not user_input:
            return []

        # 計算每個情境的匹配分數
        scores: Dict[str, int] = {}

        for keyword, scenarios in self.keyword_index.items():
            if keyword in user_input:
                for scenario in scenarios:
                    scores[scenario] = scores.get(scenario, 0) + 1

        # 按分數排序
        sorted_scenarios = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [s[0] for s in sorted_scenarios]

    def get_examples_for_context(
        self,
        context: str,
        max_examples: int = 3,
    ) -> List[Dict[str, Any]]:
        """取得特定情境的範例

        Args:
            context: 情境名稱（中文或英文 ID）
            max_examples: 最多回傳幾個範例

        Returns:
            範例列表，每個範例包含 question, speakers, patient_responses
        """
        # 處理英文 ID 轉中文
        if context in self.CONTEXT_MAPPING_REVERSE:
            context = self.CONTEXT_MAPPING_REVERSE[context]

        questions = self.scenarios.get(context, [])
        if not questions:
            return []

        # 回傳前 N 個
        return questions[:max_examples]

    def get_examples(
        self,
        user_input: str,
        previous_context: Optional[str] = None,
        max_examples: int = 5,
    ) -> List[Dict[str, Any]]:
        """載入 few-shot 範例（基於情境）

        Args:
            user_input: 當前使用者輸入
            previous_context: 上一輪推理出的情境
            max_examples: 最多回傳幾個範例

        Returns:
            範例列表
        """
        examples = []

        # 1. 如果有上一輪的情境，優先載入該情境的範例
        if previous_context:
            matched = self.get_examples_for_context(
                context=previous_context,
                max_examples=3,
            )
            examples.extend(matched)

        # 2. 用關鍵字匹配補充其他可能的情境
        if len(examples) < max_examples:
            keyword_matches = self.find_by_keywords(user_input)
            for scenario in keyword_matches[:2]:
                # 避免重複載入同一情境
                if scenario != previous_context:
                    additional = self.get_examples_for_context(
                        context=scenario,
                        max_examples=2,
                    )
                    examples.extend(additional)

                if len(examples) >= max_examples:
                    break

        return examples[:max_examples]

    def format_examples_for_prompt(self, examples: List[Dict[str, Any]]) -> str:
        """將範例格式化為 prompt 片段

        Args:
            examples: 範例列表

        Returns:
            格式化後的字串
        """
        if not examples:
            return ""

        lines = ["[情境範例]"]
        for ex in examples:
            speaker = ex.get("speakers", ["對話方"])[0]
            question = ex.get("question", "")
            responses = ex.get("patient_responses", [])[:2]  # 只取前 2 個

            if question and responses:
                lines.append(f"{speaker}問：{question}")
                lines.append(f"病患可能回答：{' / '.join(responses)}")

        return "\n".join(lines)

    def get_all_speakers(self) -> List[str]:
        """取得所有可用的 speaker 角色

        Returns:
            speaker 角色列表
        """
        return list(self.speaker_index.keys())

    def get_scenarios_summary(self) -> str:
        """取得情境摘要（供 LLM 參考）

        Returns:
            情境摘要字串
        """
        lines = []
        for scenario_name, questions in self.scenarios.items():
            # 收集該情境下的所有 speakers
            speakers = set()
            for q in questions:
                speakers.update(q.get("speakers", []))

            speakers_str = "、".join(sorted(speakers))
            lines.append(f"- {scenario_name}（{speakers_str}）")

        return "\n".join(lines)

    def get_context_id(self, context_name: str) -> str:
        """將中文情境名稱轉為英文 ID

        Args:
            context_name: 中文情境名稱

        Returns:
            英文 ID，如果找不到則回傳原名
        """
        return self.CONTEXT_MAPPING.get(context_name, context_name)

    def get_context_name(self, context_id: str) -> str:
        """將英文 ID 轉為中文情境名稱

        Args:
            context_id: 英文 ID

        Returns:
            中文情境名稱，如果找不到則回傳原 ID
        """
        return self.CONTEXT_MAPPING_REVERSE.get(context_id, context_id)

    def get_bootstrap_examples(self) -> List[Dict[str, Any]]:
        """取得第一輪對話用的預設範例（多角色覆蓋）

        用於解決第一輪對話的「雞生蛋」問題：
        沒有 previous_context → 無法載入對應 few-shot → LLM 推理不準

        Returns:
            包含物理治療師、營養師、護理師、醫師、照顧者範例的列表
        """
        return self.BOOTSTRAP_EXAMPLES.copy()


# 單例模式
_scenario_manager_instance: Optional[ScenarioManager] = None


def get_scenario_manager() -> ScenarioManager:
    """取得 ScenarioManager 單例

    Returns:
        ScenarioManager 實例
    """
    global _scenario_manager_instance
    if _scenario_manager_instance is None:
        _scenario_manager_instance = ScenarioManager()
    return _scenario_manager_instance


# 測試函數
def test_scenario_manager():
    """測試 ScenarioManager 基本功能"""
    print("🧪 測試 ScenarioManager...")

    try:
        sm = ScenarioManager()

        # 測試載入
        print(f"\n1. 載入測試:")
        print(f"   載入情境數: {len(sm.scenarios)}")
        print(f"   情境列表: {list(sm.scenarios.keys())}")

        # 測試關鍵字匹配
        print(f"\n2. 關鍵字匹配測試:")
        test_inputs = ["你今天吃了什麼？", "傷口還會痛嗎？", "等等要做什麼檢查？"]
        for input_text in test_inputs:
            matches = sm.find_by_keywords(input_text)
            print(f"   '{input_text}' → {matches[:2]}")

        # 測試範例取得
        print(f"\n3. 範例取得測試:")
        examples = sm.get_examples_for_context("營養諮詢", max_examples=2)
        print(f"   營養諮詢範例數: {len(examples)}")
        if examples:
            print(f"   第一個問題: {examples[0].get('question', '')}")

        # 測試格式化
        print(f"\n4. 格式化測試:")
        formatted = sm.format_examples_for_prompt(examples)
        print(formatted)

        # 測試情境列表
        print(f"\n5. 情境列表:")
        print(f"   {list(sm.scenarios.keys())}")

        print("\n✅ ScenarioManager 測試完成")
        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_scenario_manager()
