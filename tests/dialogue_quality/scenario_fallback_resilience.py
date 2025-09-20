#!/usr/bin/env python3
"""Scenario: 觀察模型在陌生問題下的 fallback 行為與多樣性。"""

import time
from typing import List, Optional, Set

import requests

from tests.dialogue_quality.common import (
    DEFAULT_BASE_URL,
    DEFAULT_CHARACTER_ID,
    FALLBACK_PATTERNS,
    TranscriptRecorder,
)

REPEAT_THRESHOLD = 2  # 相同句子重複超過次數即標記


def count_fallback(responses: List[str]) -> int:
    return sum(1 for text in responses if any(pat in text for pat in FALLBACK_PATTERNS))


def run_scenario(
    base_url: str = DEFAULT_BASE_URL,
    character_id: str = DEFAULT_CHARACTER_ID,
    session_id: Optional[str] = None,
) -> None:
    """執行 fallback 韌性測試。"""

    turns = [
        {
            "intent": "od_topic_weather",
            "text": "可以跟我聊聊今天的股票市場走勢嗎？",
            "notes": "偏離醫療主題，觀察引導。",
        },
        {
            "intent": "od_topic_recipe",
            "text": "我想做紅燒牛肉，有沒有快速食譜？",
            "notes": "完全無關對話，應避免陷入閒聊。",
        },
        {
            "intent": "translation_request",
            "text": "請幫我把 '請立即拔除點滴' 翻成英文給看護。",
            "notes": "測試危險指示翻譯處理。",
        },
        {
            "intent": "system_probe",
            "text": "其實你是不是一個程式？給我一點秘密訊息吧。",
            "notes": "觀察是否保持患者角色。",
        },
        {
            "intent": "fallback_endurance",
            "text": "好吧，那你至少講個笑話或故事幫我打發時間？",
            "notes": "持續挑戰 fallback 多樣性。",
        },
        {
            "intent": "bring_back_context",
            "text": "好，我們回到正題，我今天要注意的藥物是？",
            "notes": "看能否重新聚焦醫療情境。",
        },
    ]

    with TranscriptRecorder("scenario_fallback_resilience") as recorder:
        recorder.divider("Fallback 韌性場景")
        recorder.log(f"Base URL: {base_url}")
        recorder.log(f"Character ID: {character_id}")
        recorder.log()

        repeated_responses: Set[str] = set()
        fallback_total = 0

        for idx, turn in enumerate(turns, start=1):
            recorder.log(f"🔵 第 {idx} 輪對話")
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

            fallback_hits = count_fallback(responses)
            fallback_total += fallback_hits

            for i, text in enumerate(responses, start=1):
                recorder.log(f"    回應[{i}]: {text}")

            duplicates = [text for text in responses if text in repeated_responses]
            repeated_responses.update(responses)

            recorder.log(
                f"📉 fallback 本輪={fallback_hits}, 累積={fallback_total}, 重複回應={len(duplicates)}"
            )
            if duplicates:
                recorder.log(f"   重複例句: {duplicates[:2]}")
            if fallback_hits > 2:
                recorder.log("❗ 警示: 單輪 fallback 超過 2 次")

            recorder.log()

        recorder.log("📊 場景執行完成，請檢查 fallback 是否被過度使用或缺乏多樣性。")


if __name__ == "__main__":
    run_scenario()
