"""
ScenarioManager 單元測試

驗證 prompts/scenarios/ YAML 載入與查詢功能
"""

import pytest
from src.core.scenario_manager import ScenarioManager, get_scenario_manager


class TestScenarioManagerLoading:
    """測試 YAML 載入功能"""

    def test_load_all_scenarios(self):
        """驗證能載入所有 13 個 scenario YAML"""
        sm = ScenarioManager()
        assert len(sm.scenarios) == 13, f"預期 13 個情境，實際 {len(sm.scenarios)}"

    def test_scenario_names_exist(self):
        """驗證關鍵情境名稱存在"""
        sm = ScenarioManager()
        expected_scenarios = ["病房日常", "營養諮詢", "醫師查房", "傷口管路相關", "生命徵象"]
        for scenario in expected_scenarios:
            assert scenario in sm.scenarios, f"情境 '{scenario}' 不存在"

    def test_questions_structure(self):
        """驗證問題結構正確"""
        sm = ScenarioManager()
        for scenario_name, questions in sm.scenarios.items():
            assert isinstance(questions, list), f"{scenario_name}: questions 應為 list"
            for q in questions:
                assert "question" in q, f"{scenario_name}: 缺少 question 欄位"
                assert "keywords" in q, f"{scenario_name}: 缺少 keywords 欄位"
                assert "speakers" in q, f"{scenario_name}: 缺少 speakers 欄位"
                assert "patient_responses" in q, f"{scenario_name}: 缺少 patient_responses 欄位"


class TestKeywordIndex:
    """測試關鍵字索引功能"""

    def test_keyword_index_built(self):
        """驗證關鍵字索引正確建立"""
        sm = ScenarioManager()
        assert len(sm.keyword_index) > 0, "關鍵字索引為空"

    def test_find_by_keywords_with_matching_keyword(self):
        """驗證關鍵字匹配：有匹配的情況"""
        sm = ScenarioManager()
        # 「飲食」是營養諮詢和病房日常的關鍵字
        scenarios = sm.find_by_keywords("飲食")
        assert len(scenarios) > 0, "應該找到匹配的情境"
        assert "營養諮詢" in scenarios or "病房日常" in scenarios

    def test_find_by_keywords_with_no_match(self):
        """驗證關鍵字匹配：無匹配的情況"""
        sm = ScenarioManager()
        scenarios = sm.find_by_keywords("完全不相關的詞彙xyz")
        assert scenarios == [], "不應該找到任何匹配"

    def test_find_by_keywords_multiple_matches(self):
        """驗證多個關鍵字的情況"""
        sm = ScenarioManager()
        # 「傷口」應該匹配到多個情境
        scenarios = sm.find_by_keywords("傷口痛")
        assert len(scenarios) >= 1, "應該找到至少一個匹配的情境"


class TestSpeakerIndex:
    """測試 Speaker 索引功能"""

    def test_speaker_index_built(self):
        """驗證 speaker 索引正確建立"""
        sm = ScenarioManager()
        assert len(sm.speaker_index) > 0, "speaker 索引為空"

    def test_get_all_speakers(self):
        """驗證取得所有 speaker 角色"""
        sm = ScenarioManager()
        speakers = sm.get_all_speakers()
        assert "護理師" in speakers
        assert "醫師" in speakers
        assert "營養師" in speakers


class TestExamplesRetrieval:
    """測試範例取得功能"""

    def test_get_examples_for_context(self):
        """驗證取得特定情境的範例"""
        sm = ScenarioManager()
        examples = sm.get_examples_for_context("營養諮詢", max_examples=3)
        assert len(examples) <= 3, "不應超過 max_examples"
        assert len(examples) > 0, "應該有範例"

    def test_get_examples_with_english_id(self):
        """驗證使用英文 ID 也能取得範例"""
        sm = ScenarioManager()
        examples = sm.get_examples_for_context("nutrition_examples", max_examples=2)
        assert len(examples) > 0, "使用英文 ID 應該也能取得範例"

    def test_get_examples_smart_loading(self):
        """驗證智慧載入邏輯"""
        sm = ScenarioManager()
        examples = sm.get_examples(
            user_input="傷口",
            previous_context=None,
            max_examples=3,
        )
        assert len(examples) > 0, "應該找到範例"

    def test_get_examples_with_previous_context(self):
        """驗證有上一輪情境時的載入"""
        sm = ScenarioManager()
        examples = sm.get_examples(
            user_input="任意輸入",
            previous_context="營養諮詢",
            max_examples=5,
        )
        # 應該優先載入上一輪情境的範例
        assert len(examples) > 0


class TestFormatting:
    """測試格式化功能"""

    def test_format_examples_for_prompt(self):
        """驗證範例格式化輸出"""
        sm = ScenarioManager()
        examples = sm.get_examples("飲食", max_examples=2)
        formatted = sm.format_examples_for_prompt(examples)

        assert "[情境範例]" in formatted
        assert "問：" in formatted
        assert "病患可能回答：" in formatted

    def test_format_empty_examples(self):
        """驗證空範例的格式化"""
        sm = ScenarioManager()
        formatted = sm.format_examples_for_prompt([])
        assert formatted == ""


class TestContextMapping:
    """測試情境名稱轉換"""

    def test_get_context_id(self):
        """驗證中文轉英文 ID"""
        sm = ScenarioManager()
        assert sm.get_context_id("病房日常") == "daily_routine_examples"
        assert sm.get_context_id("營養諮詢") == "nutrition_examples"

    def test_get_context_name(self):
        """驗證英文 ID 轉中文"""
        sm = ScenarioManager()
        assert sm.get_context_name("daily_routine_examples") == "病房日常"
        assert sm.get_context_name("nutrition_examples") == "營養諮詢"


class TestSingleton:
    """測試單例模式"""

    def test_get_scenario_manager_singleton(self):
        """驗證 get_scenario_manager 回傳同一實例"""
        sm1 = get_scenario_manager()
        sm2 = get_scenario_manager()
        assert sm1 is sm2, "應該回傳同一實例"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
