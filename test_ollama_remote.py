#!/usr/bin/env python
"""
測試遠端 Ollama 服務器 (120.126.94.197) 上的 gpt-oss:20b 模型
"""

import requests
import json
import logging
from typing import Dict, Any
import time
import socket
import os

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ollama 服務器配置 - 支援環境變數覆寫
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "120.126.94.197")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")

logger.info(f"配置資訊:")
logger.info(f"  OLLAMA_HOST: {OLLAMA_HOST}")
logger.info(f"  OLLAMA_PORT: {OLLAMA_PORT}")
logger.info(f"  MODEL_NAME: {MODEL_NAME}")

def test_network_connectivity():
    """測試基本網路連通性"""
    try:
        logger.info(f"測試 DNS 解析 {OLLAMA_HOST}...")
        ip_address = socket.gethostbyname(OLLAMA_HOST)
        logger.info(f"✅ DNS 解析成功: {OLLAMA_HOST} -> {ip_address}")

        logger.info(f"測試 TCP 連接到 {OLLAMA_HOST}:{OLLAMA_PORT}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((OLLAMA_HOST, OLLAMA_PORT))
        sock.close()

        if result == 0:
            logger.info(f"✅ TCP 連接成功")
            return True
        else:
            logger.error(f"❌ TCP 連接失敗 (錯誤碼: {result})")
            return False
    except socket.gaierror as e:
        logger.error(f"❌ DNS 解析失敗: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ 網路測試錯誤: {str(e)}")
        return False

def test_ollama_connection():
    """測試 Ollama 服務器連線"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json()
            logger.info(f"✅ 成功連接到 Ollama 服務器")
            logger.info(f"可用模型列表:")
            for model in models.get('models', []):
                logger.info(f"  - {model.get('name')}")
            return True
        else:
            logger.error(f"❌ 連接失敗: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ 連接錯誤: {str(e)}")
        return False

def test_generate_response(prompt: str) -> Dict[str, Any]:
    """測試生成回應"""
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 500
        }
    }

    try:
        logger.info(f"發送請求到: {url}")
        logger.info(f"使用模型: {MODEL_NAME}")
        logger.info(f"Prompt: {prompt[:100]}...")

        start_time = time.time()
        response = requests.post(url, json=payload, timeout=60)
        end_time = time.time()

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ 生成成功 (耗時: {end_time - start_time:.2f}秒)")
            return {
                "success": True,
                "response": result.get("response", ""),
                "duration": end_time - start_time,
                "model": result.get("model", ""),
                "created_at": result.get("created_at", ""),
                "total_duration": result.get("total_duration", 0) / 1e9 if result.get("total_duration") else 0
            }
        else:
            logger.error(f"❌ 生成失敗: HTTP {response.status_code}")
            logger.error(f"錯誤訊息: {response.text}")
            return {"success": False, "error": f"HTTP {response.status_code}"}

    except requests.exceptions.Timeout:
        logger.error("❌ 請求超時 (60秒)")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        logger.error(f"❌ 發生錯誤: {str(e)}")
        return {"success": False, "error": str(e)}

def test_chat_completion(messages: list) -> Dict[str, Any]:
    """測試對話模式"""
    url = f"{OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }

    try:
        logger.info(f"測試對話模式...")
        logger.info(f"訊息數量: {len(messages)}")

        start_time = time.time()
        response = requests.post(url, json=payload, timeout=60)
        end_time = time.time()

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ 對話生成成功 (耗時: {end_time - start_time:.2f}秒)")
            return {
                "success": True,
                "message": result.get("message", {}),
                "duration": end_time - start_time,
                "total_duration": result.get("total_duration", 0) / 1e9 if result.get("total_duration") else 0
            }
        else:
            logger.error(f"❌ 對話生成失敗: HTTP {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}

    except Exception as e:
        logger.error(f"❌ 對話錯誤: {str(e)}")
        return {"success": False, "error": str(e)}

def run_comprehensive_tests():
    """執行完整測試套件"""
    logger.info("=" * 60)
    logger.info("開始測試 Ollama gpt-oss:20b 模型")
    logger.info(f"服務器: {OLLAMA_BASE_URL}")
    logger.info("=" * 60)

    # 測試 0: 網路連通性測試
    logger.info("\n[測試 0] 網路連通性測試")
    if not test_network_connectivity():
        logger.error("網路連接問題，請檢查:")
        logger.error("1. 服務器 IP 是否正確")
        logger.error("2. Ollama 服務是否在運行")
        logger.error("3. 防火牆是否開放 11434 端口")
        logger.error("4. Docker 容器是否能訪問外部網路")

    # 測試 1: 連線測試
    logger.info("\n[測試 1] Ollama API 連線測試")
    if not test_ollama_connection():
        logger.error("無法連接到 Ollama 服務器 API")
        logger.info("嘗試使用替代方法...")

        # 嘗試直接測試生成 API
        logger.info("直接測試 /api/generate endpoint...")
        test_result = test_generate_response("Hi")
        if not test_result["success"]:
            logger.error("無法使用 Ollama 服務，終止測試")
            return
        else:
            logger.info("✅ 直接生成測試成功，繼續其他測試")
            return

    # 測試 2: 簡單生成測試
    logger.info("\n[測試 2] 簡單文字生成")
    result = test_generate_response("What is the capital of France? Answer in one word.")
    if result["success"]:
        logger.info(f"回應: {result['response'][:200]}")
        logger.info(f"模型處理時間: {result.get('total_duration', 0):.2f}秒")

    # 測試 3: 中文生成測試
    logger.info("\n[測試 3] 中文生成測試")
    result = test_generate_response("請用繁體中文簡單介紹台灣的特色，約50字。")
    if result["success"]:
        logger.info(f"回應: {result['response'][:300]}")

    # 測試 4: 對話模式測試
    logger.info("\n[測試 4] 對話模式測試")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "2+2 equals 4."},
        {"role": "user", "content": "What about 3+3?"}
    ]
    result = test_chat_completion(messages)
    if result["success"]:
        logger.info(f"回應: {result['message'].get('content', '')[:200]}")

    # 測試 5: 角色扮演測試（醫療情境）
    logger.info("\n[測試 5] 角色扮演測試")
    medical_prompt = """你是一位名叫李先生的病患，65歲，患有高血壓。
醫生問你：「李先生，您最近有按時服藥嗎？」
請以病患的身份回答，約30字。"""

    result = test_generate_response(medical_prompt)
    if result["success"]:
        logger.info(f"回應: {result['response']}")

    # 測試 6: JSON 格式輸出測試
    logger.info("\n[測試 6] JSON 格式輸出測試")
    json_prompt = """Generate a JSON object with the following structure:
{
  "name": "a person's name",
  "age": a number between 20 and 80,
  "city": "a city name"
}
Only output valid JSON, nothing else."""

    result = test_generate_response(json_prompt)
    if result["success"]:
        logger.info(f"回應: {result['response']}")
        try:
            parsed = json.loads(result['response'])
            logger.info(f"✅ JSON 解析成功: {parsed}")
        except:
            logger.warning("⚠️ 無法解析為 JSON")

    # 測試 7: 效能測試（多次請求）
    logger.info("\n[測試 7] 效能測試（3次請求）")
    durations = []
    for i in range(3):
        start = time.time()
        result = test_generate_response(f"Count from 1 to 5. Request #{i+1}")
        duration = time.time() - start
        durations.append(duration)
        logger.info(f"  請求 {i+1}: {duration:.2f}秒")

    avg_duration = sum(durations) / len(durations)
    logger.info(f"平均回應時間: {avg_duration:.2f}秒")

    logger.info("\n" + "=" * 60)
    logger.info("測試完成！")
    logger.info("=" * 60)

if __name__ == "__main__":
    try:
        run_comprehensive_tests()
    except KeyboardInterrupt:
        logger.info("\n測試被使用者中斷")
    except Exception as e:
        logger.error(f"測試過程發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()