#!/usr/bin/env python3
"""Scenario: 模擬語音轉文字雜訊與打字錯誤，檢查魯棒性。"""

import time
from typing import List, Optional

import requests

from tests.dialogue_quality.common import (
    DEFAULT_BASE_URL,
    DEFAULT_CHARACTER_ID,
    FALLBACK_PATTERNS,
    TranscriptRecorder,
)

CLARIFICATION_KEYWORDS = ["再說一次", "請再", "請問", "不太清楚", "能不能說明"]


def detect_noise_handling(responses: List[str]) -> dict:
    """回傳模型是否先澄清、直接回答或使用 fallback。"""

    flags = {"clarify": 0, "fallback": 0}
    for text in responses:
        if any(keyword in text for keyword in CLARIFICATION_KEYWORDS):
            flags["clarify"] += 1
        if any(pattern in text for pattern in FALLBACK_PATTERNS):
            flags["fallback"] += 1
    return flags


def run_scenario(
    base_url: str = DEFAULT_BASE_URL,
    character_id: str = DEFAULT_CHARACTER_ID,
    session_id: Optional[str] = None,
) -> None:
    """執行噪音輸入測試。"""

    turns = [
        {
            "intent": "greeting_with_noise",
            "text": "哈囉～（有點喘）這裡天氣好熱 uh 你好嗎",
            "notes": "低噪音，預期能理解。",
            "noise_level": "low",
        },
        {
            "intent": "symptom_noise",
            "text": "頭暈 一直轉像 起床會噁 可能?",
            "notes": "刪去助詞、語法破碎。",
            "noise_level": "medium",
        },
        {
            "intent": "med_name_collision",
            "text": "剛剛醫生說要吃Ateno呃 atenolol 還是atorvastatin?",
            "notes": "拼字錯誤與不完整詞。",
            "noise_level": "high",
        },
        {
            "intent": "numerical_noise",
            "text": "血壓剛剛 1-5-0 over 9? 9還是 98?",
            "notes": "數字被切割。",
            "noise_level": "high",
        },
        {
            "intent": "closing",
            "text": "謝謝你 那我先休息 有什麼要注意 de嗎",
            "notes": "帶有語尾噪音，期待能整理出提醒。",
            "noise_level": "low",
        },
    ]

    with TranscriptRecorder("scenario_noisy_input") as recorder:
        recorder.divider("噪音輸入魯棒性場景")
        recorder.log(f"Base URL: {base_url}")
        recorder.log(f"Character ID: {character_id}")
        recorder.log()

        for idx, turn in enumerate(turns, start=1):
            recorder.log(
                f"🔵 第 {idx} 輪對話 (noise={turn['noise_level']})"
            )
            recorder.log(f"  意圖: {turn['intent']}")
            recorder.log(f"  說明: {turn['notes']}")
            recorder.log(f"護理人員: {turn['text']}")

            try:
                start_time = time.time()
                response = requests.post(
                    f"{base_url}/api/dialogue/text",
                    headers={"Content-Type": "application/json"},
                    json={
                        "text": turn["text"],
                        "character_id": character_id,
                        "session_id": session_id,
                        "response_format": "text",
                    },
                    timeout=30,
                )
                elapsed = time.time() - start_time
            except Exception as exc:  # pragma: no cover - network failure reporting
                recorder.log(f"❌ 請求失敗: {exc}")
                break

            if response.status_code != 200:
                recorder.log(f"❌ HTTP 狀態碼 {response.status_code}")
                recorder.log(f"回應內容: {response.text[:200]}")
                break

            payload = response.json()
            session_id = payload.get("session_id", session_id)
            responses = payload.get("responses", [])

            recorder.log(f"✅ 回應時間: {elapsed:.2f}s")
            recorder.log(f"🆔 Session ID: {session_id or '尚未建立'}")
            recorder.log(f"🎭 狀態: {payload.get('state', 'UNKNOWN')}")
            recorder.log(f"🌍 情境: {payload.get('dialogue_context', 'UNKNOWN')}")

            flags = detect_noise_handling(responses)
            for i, text in enumerate(responses, start=1):
                recorder.log(f"    回應[{i}]: {text}")

            recorder.log(
                f"📉 噪音處理: clarify={flags['clarify']}, fallback={flags['fallback']}"
            )
            if flags["fallback"] and turn["noise_level"] == "low":
                recorder.log("❗ 警示: 低噪音卻啟動 fallback，需檢查理解能力")
            if flags["clarify"] == 0 and turn["noise_level"] == "high":
                recorder.log("❗ 警示: 高噪音卻未請求澄清")

            recorder.log()

        recorder.log("📊 場景執行完成，請評估每輪回應對噪音的處理品質。")


if __name__ == "__main__":
    run_scenario()
