#!/usr/bin/env python
"""
測試 DSPy 與遠端 Ollama (gpt-oss:20b) 的整合
"""

import sys
import os
sys.path.insert(0, '/app/src')

import dspy
import logging
import time
from typing import List, Dict
from src.llm.dspy_ollama_adapter import DSPyOllamaLM

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ollama 配置
OLLAMA_BASE_URL = "http://120.126.94.197:11434"
MODEL_NAME = "gpt-oss:20b"

def setup_dspy_with_ollama():
    """配置 DSPy 使用 Ollama"""
    try:
        # 使用專案的 DSPyOllamaLM 適配器
        config_override = {
            "base_url": OLLAMA_BASE_URL,
            "model": MODEL_NAME,
            "temperature": 0.7,
            "timeout": 30
        }

        lm = DSPyOllamaLM.from_config(config_override)
        dspy.settings.configure(lm=lm)

        logger.info(f"✅ DSPy 配置成功")
        logger.info(f"  模型: {MODEL_NAME}")
        logger.info(f"  服務器: {OLLAMA_BASE_URL}")
        return True
    except Exception as e:
        logger.error(f"❌ DSPy 配置失敗: {str(e)}")
        return False

# 定義 DSPy Signatures
class SimpleQA(dspy.Signature):
    """回答簡單問題"""
    question = dspy.InputField()
    answer = dspy.OutputField()

class PatientResponse(dspy.Signature):
    """生成病患回應"""
    doctor_question = dspy.InputField(desc="醫生的問題")
    patient_info = dspy.InputField(desc="病患資訊")
    response = dspy.OutputField(desc="病患的回應")

class DialogueGeneration(dspy.Signature):
    """生成對話回應選項"""
    user_input = dspy.InputField(desc="使用者輸入")
    character_name = dspy.InputField(desc="角色名稱")
    character_persona = dspy.InputField(desc="角色個性")
    responses = dspy.OutputField(desc="5個不同的回應選項，用分號分隔")

def test_simple_qa():
    """測試簡單問答"""
    logger.info("\n[測試] 簡單問答")

    try:
        qa = dspy.Predict(SimpleQA)

        questions = [
            "What is 2+2?",
            "台灣的首都是哪裡？",
            "Name one programming language."
        ]

        for q in questions:
            start_time = time.time()
            result = qa(question=q)
            duration = time.time() - start_time

            logger.info(f"問題: {q}")
            logger.info(f"回答: {result.answer}")
            logger.info(f"耗時: {duration:.2f}秒")
            logger.info("-" * 40)

        return True
    except Exception as e:
        logger.error(f"簡單問答測試失敗: {str(e)}")
        return False

def test_patient_response():
    """測試病患回應生成"""
    logger.info("\n[測試] 病患回應生成")

    try:
        patient_module = dspy.Predict(PatientResponse)

        test_cases = [
            {
                "doctor_question": "李先生，您最近有按時服藥嗎？",
                "patient_info": "李先生，65歲，高血壓患者，平時記性不太好"
            },
            {
                "doctor_question": "您的胸痛持續多久了？",
                "patient_info": "王太太，55歲，最近工作壓力大，偶爾胸悶"
            }
        ]

        for case in test_cases:
            start_time = time.time()
            result = patient_module(
                doctor_question=case["doctor_question"],
                patient_info=case["patient_info"]
            )
            duration = time.time() - start_time

            logger.info(f"醫生問題: {case['doctor_question']}")
            logger.info(f"病患資訊: {case['patient_info']}")
            logger.info(f"病患回應: {result.response}")
            logger.info(f"耗時: {duration:.2f}秒")
            logger.info("-" * 40)

        return True
    except Exception as e:
        logger.error(f"病患回應測試失敗: {str(e)}")
        return False

def test_dialogue_generation():
    """測試對話生成"""
    logger.info("\n[測試] 對話生成（多選項）")

    try:
        dialogue = dspy.Predict(DialogueGeneration)

        test_case = {
            "user_input": "我最近胸口有點悶",
            "character_name": "Patient_A",
            "character_persona": "一位關心自己健康但容易緊張的中年人"
        }

        start_time = time.time()
        result = dialogue(
            user_input=test_case["user_input"],
            character_name=test_case["character_name"],
            character_persona=test_case["character_persona"]
        )
        duration = time.time() - start_time

        logger.info(f"使用者輸入: {test_case['user_input']}")
        logger.info(f"角色: {test_case['character_name']}")
        logger.info(f"個性: {test_case['character_persona']}")
        logger.info(f"生成的回應選項:")

        # 解析回應選項
        responses = result.responses.split(';')
        for i, resp in enumerate(responses, 1):
            logger.info(f"  {i}. {resp.strip()}")

        logger.info(f"耗時: {duration:.2f}秒")

        return True
    except Exception as e:
        logger.error(f"對話生成測試失敗: {str(e)}")
        return False

def test_chain_of_thought():
    """測試思維鏈（Chain of Thought）"""
    logger.info("\n[測試] 思維鏈推理")

    class ReasoningTask(dspy.Signature):
        """使用推理步驟解決問題"""
        problem = dspy.InputField()
        reasoning = dspy.OutputField(desc="詳細的推理步驟")
        answer = dspy.OutputField(desc="最終答案")

    try:
        cot = dspy.ChainOfThought(ReasoningTask)

        problems = [
            "如果一個病人有高血壓，又忘記吃藥3天，可能會有什麼風險？",
            "一位60歲的糖尿病患者，應該注意哪些飲食習慣？"
        ]

        for problem in problems:
            start_time = time.time()
            result = cot(problem=problem)
            duration = time.time() - start_time

            logger.info(f"問題: {problem}")
            logger.info(f"推理過程: {result.reasoning}")
            logger.info(f"答案: {result.answer}")
            logger.info(f"耗時: {duration:.2f}秒")
            logger.info("-" * 40)

        return True
    except Exception as e:
        logger.error(f"思維鏈測試失敗: {str(e)}")
        return False

def run_all_tests():
    """執行所有測試"""
    logger.info("=" * 60)
    logger.info("開始 DSPy + Ollama (gpt-oss:20b) 整合測試")
    logger.info("=" * 60)

    # 設定 DSPy
    if not setup_dspy_with_ollama():
        logger.error("無法設定 DSPy，終止測試")
        return

    # 執行測試
    tests = [
        ("簡單問答", test_simple_qa),
        ("病患回應", test_patient_response),
        ("對話生成", test_dialogue_generation),
        ("思維鏈推理", test_chain_of_thought)
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*20} {test_name} {'='*20}")
        success = test_func()
        results.append((test_name, success))
        time.sleep(1)  # 避免過快請求

    # 總結
    logger.info("\n" + "=" * 60)
    logger.info("測試結果總結:")
    logger.info("=" * 60)

    for test_name, success in results:
        status = "✅ 成功" if success else "❌ 失敗"
        logger.info(f"{test_name}: {status}")

    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    logger.info(f"\n總計: {success_count}/{total_count} 測試通過")

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        logger.info("\n測試被使用者中斷")
    except Exception as e:
        logger.error(f"測試過程發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()