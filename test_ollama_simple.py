#!/usr/bin/env python
"""
簡單測試 Ollama gpt-oss:20b 連線與基本功能
"""

import sys
sys.path.insert(0, '/app/src')

import logging
import time
from src.llm.dspy_ollama_adapter import DSPyOllamaLM
import dspy

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ollama 配置
OLLAMA_CONFIG = {
    "base_url": "http://120.126.94.197:11434",
    "model": "gpt-oss:20b",
    "temperature": 0.7,
    "timeout": 30
}

def test_direct_ollama():
    """直接測試 Ollama 適配器"""
    logger.info("=" * 60)
    logger.info("測試 1: 直接調用 Ollama 適配器")
    logger.info("=" * 60)

    try:
        lm = DSPyOllamaLM.from_config(OLLAMA_CONFIG)

        # 測試簡單生成
        prompts = [
            "What is 2+2? Answer: ",
            "台灣的首都是",
            "The capital of France is"
        ]

        for prompt in prompts:
            logger.info(f"\nPrompt: {prompt}")
            start_time = time.time()
            response = lm(prompt)
            duration = time.time() - start_time
            logger.info(f"Response: {response[:100]}")
            logger.info(f"Duration: {duration:.2f}s")

        return True
    except Exception as e:
        logger.error(f"直接調用失敗: {str(e)}")
        return False

def test_dspy_integration():
    """測試 DSPy 整合"""
    logger.info("\n" + "=" * 60)
    logger.info("測試 2: DSPy 整合測試")
    logger.info("=" * 60)

    try:
        # 配置 DSPy
        lm = DSPyOllamaLM.from_config(OLLAMA_CONFIG)
        dspy.settings.configure(lm=lm)

        # 定義簡單 Signature
        class SimpleQA(dspy.Signature):
            """Answer questions with short answers."""
            question = dspy.InputField()
            answer = dspy.OutputField(desc="short answer")

        # 創建 Predict 模組
        qa = dspy.Predict(SimpleQA)

        # 測試問題
        questions = [
            "What is the capital of Japan?",
            "What is 5 + 3?",
            "Name one programming language."
        ]

        for q in questions:
            logger.info(f"\nQuestion: {q}")
            start_time = time.time()

            try:
                result = qa(question=q)
                duration = time.time() - start_time
                logger.info(f"Answer: {result.answer}")
                logger.info(f"Duration: {duration:.2f}s")
            except Exception as e:
                logger.error(f"Failed to answer: {str(e)}")

        return True
    except Exception as e:
        logger.error(f"DSPy 整合失敗: {str(e)}")
        return False

def test_chinese_dialogue():
    """測試中文對話生成"""
    logger.info("\n" + "=" * 60)
    logger.info("測試 3: 中文對話生成")
    logger.info("=" * 60)

    try:
        lm = DSPyOllamaLM.from_config(OLLAMA_CONFIG)
        dspy.settings.configure(lm=lm)

        class PatientDialogue(dspy.Signature):
            """Generate patient response in Traditional Chinese."""
            doctor_question = dspy.InputField(desc="醫生的問題")
            patient_background = dspy.InputField(desc="病患背景")
            response = dspy.OutputField(desc="病患回應（繁體中文）")

        patient = dspy.Predict(PatientDialogue)

        test_case = {
            "doctor_question": "您最近有按時服藥嗎？",
            "patient_background": "65歲男性，患有高血壓，記性不太好"
        }

        logger.info(f"醫生問題: {test_case['doctor_question']}")
        logger.info(f"病患背景: {test_case['patient_background']}")

        start_time = time.time()
        result = patient(
            doctor_question=test_case['doctor_question'],
            patient_background=test_case['patient_background']
        )
        duration = time.time() - start_time

        logger.info(f"病患回應: {result.response}")
        logger.info(f"Duration: {duration:.2f}s")

        return True
    except Exception as e:
        logger.error(f"中文對話測試失敗: {str(e)}")
        return False

def main():
    logger.info("開始 Ollama gpt-oss:20b 簡單測試")
    logger.info(f"服務器: {OLLAMA_CONFIG['base_url']}")
    logger.info(f"模型: {OLLAMA_CONFIG['model']}")

    results = []

    # 執行測試
    tests = [
        ("直接調用", test_direct_ollama),
        ("DSPy 整合", test_dspy_integration),
        ("中文對話", test_chinese_dialogue)
    ]

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except KeyboardInterrupt:
            logger.info("\n測試被中斷")
            break
        except Exception as e:
            logger.error(f"{test_name}發生錯誤: {str(e)}")
            results.append((test_name, False))

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
    main()