"""
LLM-as-Judge 回應品質評估器

使用 LLM 評估病患回應是否適合該對話方角色與情境。
這是 self-annotation 機制的延伸，用於品質監控。

主要評估維度：
1. Speaker 適切性：回應是否針對該角色的專業範疇
2. Context 適切性：回應是否符合該情境的期望
3. 病患視角：回應是否以第一人稱描述感受
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResponseQualityJudge:
    """使用 LLM 評估回應品質

    評估標準：
    - Speaker 適切性：回應是否針對該 speaker 的專業範疇
    - Context 適切性：回應是否符合該情境的期望
    - 病患視角：回應是否以第一人稱描述感受

    使用方式：
        judge = ResponseQualityJudge()
        result = judge.evaluate(
            user_input="嘴巴現在張得怎麼樣？",
            responses=["比較開了", "還是有點緊"],
            inferred_speaker="物理治療師",
            dialogue_context="物理治療"
        )
    """

    JUDGE_PROMPT = """你是一位對話品質評審。請評估以下病患回應是否適合該對話情境。

對話方角色：{inferred_speaker}
對話情境：{dialogue_context}
對話方問題：{user_input}

病患回應選項：
{responses}

請評估每個回應的適切性（1-5 分），並說明原因：

評估標準：
1. Speaker 適切性：回應是否針對該角色的專業範疇？
   - 物理治療師：應關注運動、張嘴、肌肉、復健動作
   - 營養師：應關注飲食、營養、體重、食慾
   - 護理師：應關注日常照護、生命徵象、基本需求
   - 醫師：應關注治療、診斷、檢查、病情
   - 照顧者：應關注情緒、日常需求、家庭關係

2. Context 適切性：回應是否符合該情境的期望？

3. 病患視角：回應是否以第一人稱描述感受（而非第三人稱或醫療專業視角）？

請輸出 JSON 格式：
{{
  "speaker_scores": [分數1, 分數2, 分數3, 分數4],
  "context_scores": [分數1, 分數2, 分數3, 分數4],
  "overall_score": 整體平均分(1-5),
  "pass": true或false (整體 >= 3.5 為 pass),
  "issues": ["問題1", "問題2"],
  "reasoning": "簡短評估說明（50字內）"
}}"""

    # 角色專屬關鍵詞（用於快速關鍵詞檢查）
    SPEAKER_KEYWORDS: Dict[str, List[str]] = {
        "物理治療師": ["張嘴", "張口", "緊", "鬆", "運動", "練習", "肌肉", "活動", "復健"],
        "營養師": ["吃", "食慾", "配方", "營養", "飲食", "體重", "熱量", "補充"],
        "護理師": ["舒服", "痛", "血壓", "體溫", "換藥", "傷口", "好"],
        "醫師": ["治療", "手術", "診斷", "檢查", "報告", "追蹤", "指數"],
        "照顧者": ["好點", "休息", "累", "想", "需要", "擔心", "精神"],
    }

    # 角色禁止關鍵詞（出現則扣分）
    SPEAKER_FORBIDDEN: Dict[str, List[str]] = {
        "物理治療師": ["吃飯", "藥物", "血壓", "檢查報告"],
        "營養師": ["張嘴", "復健動作", "傷口"],
        "護理師": ["治療方案決定", "復健計畫"],
        "醫師": ["換藥程序", "日常瑣事"],
        "照顧者": ["診斷", "檢查報告", "治療方案"],
    }

    def __init__(self, lm=None):
        """初始化 Judge

        Args:
            lm: DSPy LM 實例。如果為 None，將使用 dspy.settings.lm
        """
        self.lm = lm

    def _get_lm(self):
        """取得 LM 實例"""
        if self.lm is not None:
            return self.lm
        try:
            import dspy
            return dspy.settings.lm
        except Exception as e:
            logger.warning(f"無法取得 DSPy LM: {e}")
            return None

    def evaluate(
        self,
        user_input: str,
        responses: List[str],
        inferred_speaker: str,
        dialogue_context: str,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """評估回應品質

        Args:
            user_input: 對話方的問題
            responses: 病患回應選項列表
            inferred_speaker: 推理出的對話方角色
            dialogue_context: 對話情境
            use_llm: 是否使用 LLM 評估（False 則只用關鍵詞）

        Returns:
            評估結果字典，包含：
            - speaker_scores: 每個回應的 Speaker 適切性分數
            - context_scores: 每個回應的 Context 適切性分數
            - overall_score: 整體平均分
            - pass: 是否通過（>= 3.5）
            - issues: 發現的問題
            - reasoning: 評估說明
        """
        # 關鍵詞快速檢查（總是執行）
        keyword_result = self._keyword_check(responses, inferred_speaker)

        if not use_llm:
            return keyword_result

        # LLM 評估
        lm = self._get_lm()
        if lm is None:
            logger.warning("LLM 不可用，使用關鍵詞評估")
            return keyword_result

        try:
            return self._llm_evaluate(
                user_input, responses, inferred_speaker, dialogue_context
            )
        except Exception as e:
            logger.error(f"LLM 評估失敗: {e}")
            return keyword_result

    def _keyword_check(
        self, responses: List[str], inferred_speaker: str
    ) -> Dict[str, Any]:
        """使用關鍵詞進行快速品質檢查

        Args:
            responses: 回應列表
            inferred_speaker: 對話方角色

        Returns:
            評估結果
        """
        target_keywords = self.SPEAKER_KEYWORDS.get(inferred_speaker, [])
        forbidden_keywords = self.SPEAKER_FORBIDDEN.get(inferred_speaker, [])

        responses_text = " ".join(responses)
        issues = []

        # 計算正向匹配
        positive_hits = sum(1 for kw in target_keywords if kw in responses_text)

        # 計算負向匹配
        forbidden_hits = []
        for kw in forbidden_keywords:
            if kw in responses_text:
                forbidden_hits.append(kw)
                issues.append(f"出現不適合詞彙：{kw}")

        # 計算分數
        if target_keywords:
            base_score = (positive_hits / len(target_keywords)) * 5
        else:
            base_score = 3.0  # 無關鍵詞時給中等分數

        penalty = len(forbidden_hits) * 0.5
        overall_score = max(1.0, min(5.0, base_score - penalty))

        return {
            "speaker_scores": [overall_score] * len(responses),
            "context_scores": [overall_score] * len(responses),
            "overall_score": round(overall_score, 2),
            "pass": overall_score >= 3.5,
            "issues": issues,
            "reasoning": f"關鍵詞檢查：正向匹配 {positive_hits}/{len(target_keywords)}，禁止詞 {len(forbidden_hits)}",
            "method": "keyword",
        }

    def _llm_evaluate(
        self,
        user_input: str,
        responses: List[str],
        inferred_speaker: str,
        dialogue_context: str,
    ) -> Dict[str, Any]:
        """使用 LLM 進行深度評估

        Args:
            user_input: 對話方的問題
            responses: 回應列表
            inferred_speaker: 對話方角色
            dialogue_context: 對話情境

        Returns:
            LLM 評估結果
        """
        prompt = self.JUDGE_PROMPT.format(
            inferred_speaker=inferred_speaker,
            dialogue_context=dialogue_context,
            user_input=user_input,
            responses="\n".join(f"{i+1}. {r}" for i, r in enumerate(responses)),
        )

        lm = self._get_lm()
        result = lm(prompt)

        # 解析回應
        if hasattr(result, "text"):
            text = result.text
        elif hasattr(result, "content"):
            text = result.content
        elif isinstance(result, list) and len(result) > 0:
            text = str(result[0])
        else:
            text = str(result)

        # 嘗試提取 JSON
        try:
            # 嘗試直接解析
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # 嘗試從文本中提取 JSON
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                except json.JSONDecodeError:
                    parsed = None
            else:
                parsed = None

        if parsed is None:
            return {
                "error": "無法解析 LLM 回應",
                "raw": text[:500],
                "method": "llm_failed",
            }

        parsed["method"] = "llm"
        return parsed

    def batch_evaluate(
        self, test_cases: List[Dict[str, Any]], use_llm: bool = True
    ) -> Dict[str, Any]:
        """批量評估多個測試案例

        Args:
            test_cases: 測試案例列表，每個包含：
                - question: 對話方問題
                - responses: 回應列表
                - inferred_speaker: 推理的角色
                - dialogue_context: 對話情境
            use_llm: 是否使用 LLM 評估

        Returns:
            批量評估結果，包含：
            - total: 總案例數
            - passed: 通過數
            - pass_rate: 通過率
            - average_score: 平均分
            - details: 每個案例的詳細結果
        """
        results = []
        total_score = 0.0

        for case in test_cases:
            result = self.evaluate(
                user_input=case["question"],
                responses=case.get("responses", []),
                inferred_speaker=case.get("inferred_speaker", ""),
                dialogue_context=case.get("dialogue_context", ""),
                use_llm=use_llm,
            )
            results.append({**case, "evaluation": result})

            if "overall_score" in result:
                total_score += result["overall_score"]

        # 計算統計
        passed = sum(
            1 for r in results if r.get("evaluation", {}).get("pass", False)
        )
        avg_score = total_score / len(results) if results else 0

        return {
            "total": len(results),
            "passed": passed,
            "pass_rate": passed / len(results) if results else 0,
            "average_score": round(avg_score, 2),
            "details": results,
        }


def quick_evaluate(
    user_input: str,
    responses: List[str],
    inferred_speaker: str,
    dialogue_context: str = "",
) -> Dict[str, Any]:
    """快速評估單個回應（便捷函數）

    Args:
        user_input: 對話方問題
        responses: 回應列表
        inferred_speaker: 對話方角色
        dialogue_context: 對話情境

    Returns:
        評估結果
    """
    judge = ResponseQualityJudge()
    return judge.evaluate(
        user_input=user_input,
        responses=responses,
        inferred_speaker=inferred_speaker,
        dialogue_context=dialogue_context,
        use_llm=False,  # 快速模式只用關鍵詞
    )


# 測試函數
def test_llm_judge():
    """測試 LLM Judge 基本功能"""
    print("🧪 測試 ResponseQualityJudge...")

    judge = ResponseQualityJudge()

    # 測試案例 1：物理治療師
    result1 = judge.evaluate(
        user_input="嘴巴現在張得怎麼樣？",
        responses=["比較開了", "還是有點緊繃", "好像有進步"],
        inferred_speaker="物理治療師",
        dialogue_context="物理治療",
        use_llm=False,
    )
    print(f"\n物理治療師案例：")
    print(f"  分數: {result1.get('overall_score')}")
    print(f"  通過: {result1.get('pass')}")
    print(f"  說明: {result1.get('reasoning')}")

    # 測試案例 2：營養師
    result2 = judge.evaluate(
        user_input="營養品有在吃嗎？",
        responses=["有在吃配方奶", "沒什麼食慾"],
        inferred_speaker="營養師",
        dialogue_context="營養諮詢",
        use_llm=False,
    )
    print(f"\n營養師案例：")
    print(f"  分數: {result2.get('overall_score')}")
    print(f"  通過: {result2.get('pass')}")

    # 測試批量評估
    test_cases = [
        {
            "question": "嘴巴張得怎樣？",
            "responses": ["比較開了"],
            "inferred_speaker": "物理治療師",
            "dialogue_context": "物理治療",
        },
        {
            "question": "營養品有吃嗎？",
            "responses": ["有吃配方奶"],
            "inferred_speaker": "營養師",
            "dialogue_context": "營養諮詢",
        },
    ]
    batch_result = judge.batch_evaluate(test_cases, use_llm=False)
    print(f"\n批量評估結果：")
    print(f"  通過率: {batch_result['pass_rate']:.1%}")
    print(f"  平均分: {batch_result['average_score']}")

    print("\n✅ LLM Judge 測試完成")
    return True


if __name__ == "__main__":
    test_llm_judge()
