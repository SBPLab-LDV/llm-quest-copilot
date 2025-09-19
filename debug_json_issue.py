#!/usr/bin/env python
"""
診斷 DSPy JSONAdapter 解析問題
"""

import sys
sys.path.insert(0, '/app/src')

import logging
import json
from src.llm.dspy_ollama_adapter import DSPyOllamaLM
import dspy

# 設定日誌
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 關閉其他模組的 DEBUG 日誌
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

def test_raw_response():
    """測試原始回應"""

    # 模擬 Ollama 返回的不同格式
    test_cases = [
        # 單行 JSON
        '{"answer": "Tokyo"}',
        # 多行 JSON（有換行）
        '{\n  "answer": "Tokyo"\n}',
        # 前後有空格
        '  {"answer": "Tokyo"}  ',
        # 有 BOM 或特殊字符
        '\ufeff{"answer": "Tokyo"}',
        # 實際 Ollama 返回格式
        '{\n  "answer": "8"\n}',
    ]

    print("=" * 60)
    print("測試不同 JSON 格式")
    print("=" * 60)

    for i, response in enumerate(test_cases, 1):
        print(f"\nCase {i}: repr={repr(response)}")
        print(f"  Length: {len(response)}")
        print(f"  First char: {repr(response[0]) if response else 'empty'}")
        print(f"  Last char: {repr(response[-1]) if response else 'empty'}")

        # 測試 JSON 解析
        try:
            parsed = json.loads(response)
            print(f"  ✅ JSON Parse OK: {parsed}")
        except json.JSONDecodeError as e:
            print(f"  ❌ JSON Error: {e}")

        # 測試 strip 後
        stripped = response.strip()
        if stripped != response:
            print(f"  After strip: repr={repr(stripped)}")
            try:
                parsed = json.loads(stripped)
                print(f"  ✅ Stripped JSON OK: {parsed}")
            except json.JSONDecodeError as e:
                print(f"  ❌ Stripped JSON Error: {e}")

def test_dspy_adapter_parsing():
    """測試 DSPy 適配器的解析邏輯"""

    print("\n" + "=" * 60)
    print("測試 DSPy Adapter 解析")
    print("=" * 60)

    # 配置
    config = {
        "base_url": "http://120.126.94.197:11434",
        "model": "gpt-oss:20b",
        "temperature": 0.7,
        "timeout": 30
    }

    # 初始化適配器
    lm = DSPyOllamaLM.from_config(config)

    # 測試 _clean_markdown_json 方法
    test_responses = [
        '{"answer": "Tokyo"}',
        '```json\n{"answer": "Tokyo"}\n```',
        '```\n{"answer": "Tokyo"}\n```',
        '{\n  "answer": "Tokyo"\n}',
    ]

    print("\nTesting _clean_markdown_json:")
    for resp in test_responses:
        print(f"  Input: {repr(resp[:50])}")
        cleaned = lm._clean_markdown_json(resp)
        print(f"  Output: {repr(cleaned[:50])}")
        if cleaned != resp:
            print(f"  ✅ Cleaned!")
        else:
            print(f"  ⚠️ No change")

def test_dspy_json_adapter():
    """直接測試 DSPy 的 JSONAdapter"""

    print("\n" + "=" * 60)
    print("測試 DSPy JSONAdapter")
    print("=" * 60)

    try:
        from dspy.adapters import JSONAdapter

        # 創建 JSONAdapter
        adapter = JSONAdapter()

        # 模擬 DSPy 的 signature
        class TestSignature(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        # 測試不同的回應格式
        test_responses = [
            '{"answer": "Tokyo"}',
            '{\n  "answer": "Tokyo"\n}',
            '{"answer":"Tokyo"}',
            '{  "answer"  :  "Tokyo"  }',
        ]

        print("\nTesting JSONAdapter.parse:")
        for resp in test_responses:
            print(f"\n  Response: {repr(resp)}")
            try:
                # 模擬 DSPy 的解析過程
                import json
                parsed = json.loads(resp)
                print(f"  Parsed JSON: {parsed}")

                # 檢查是否有 answer 欄位
                if "answer" in parsed:
                    print(f"  ✅ Has 'answer' field: {parsed['answer']}")
                else:
                    print(f"  ❌ Missing 'answer' field")
            except Exception as e:
                print(f"  ❌ Parse error: {e}")

    except ImportError as e:
        print(f"無法導入 JSONAdapter: {e}")

def inspect_actual_response():
    """檢查實際的 Ollama 回應內容"""

    print("\n" + "=" * 60)
    print("檢查實際 Ollama 回應")
    print("=" * 60)

    # 實際執行一次調用並檢查原始回應
    config = {
        "base_url": "http://120.126.94.197:11434",
        "model": "gpt-oss:20b",
        "temperature": 0.7,
        "timeout": 30
    }

    lm = DSPyOllamaLM.from_config(config)
    dspy.settings.configure(lm=lm)

    class SimpleQA(dspy.Signature):
        question = dspy.InputField()
        answer = dspy.OutputField()

    qa = dspy.Predict(SimpleQA)

    try:
        # 執行查詢
        print("\nExecuting query: 'What is 1+1?'")
        result = qa(question="What is 1+1?")
        print(f"✅ Success! Answer: {result.answer}")
    except Exception as e:
        print(f"❌ Failed: {e}")

        # 嘗試直接調用看看回應
        print("\n直接調用 LM 測試:")
        prompt = "Answer in JSON format: {\"answer\": \"...\"}\nWhat is 1+1?"
        response = lm(prompt)
        print(f"Raw response type: {type(response)}")
        print(f"Raw response repr: {repr(response[:200] if isinstance(response, str) else response)}")

        # 分析回應
        if isinstance(response, str):
            print(f"\nResponse analysis:")
            print(f"  Length: {len(response)}")
            print(f"  Starts with '{{': {response.strip().startswith('{')}")
            print(f"  Ends with '}}': {response.strip().endswith('}')}")
            print(f"  Contains 'answer': {'answer' in response}")

            # 嘗試解析
            try:
                parsed = json.loads(response)
                print(f"  ✅ Valid JSON: {parsed}")
            except json.JSONDecodeError as je:
                print(f"  ❌ Invalid JSON: {je}")
                print(f"  Error position: {je.pos if hasattr(je, 'pos') else 'unknown'}")

if __name__ == "__main__":
    test_raw_response()
    test_dspy_adapter_parsing()
    test_dspy_json_adapter()
    inspect_actual_response()