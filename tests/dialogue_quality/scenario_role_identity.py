#!/usr/bin/env python3
"""Scenario: verify the patient角色設定在多輪對話中是否保持一致。"""
import time
from typing import Dict, List, Optional

import requests

from tests.dialogue_quality.common import (
    DEFAULT_BASE_URL,
    DEFAULT_CHARACTER_ID,
    FALLBACK_PATTERNS,
    SELF_INTRO_PATTERNS,
    TranscriptRecorder,
)

ROLE_DRIFT_PATTERNS = [
    "我是護理師",
    "我是護士",
    "我是醫生",
    "我是AI",
    "作為AI",
]


def detect_role_flags(responses: List[str]) -> Dict[str, List[str]]:
    """Highlight signals that可能出現角色錯置。"""

    hits: Dict[str, List[str]] = {
        "self_intro": [],
        "role_drift": [],
        "fallback": [],
    }

    for text in responses:
        if any(pattern in text for pattern in SELF_INTRO_PATTERNS):
            hits["self_intro"].append(text)
        if any(pattern in text for pattern in ROLE_DRIFT_PATTERNS):
            hits["role_drift"].append(text)
        if any(pattern in text for pattern in FALLBACK_PATTERNS):
            hits["fallback"].append(text)
    return hits


def run_scenario(
    base_url: str = DEFAULT_BASE_URL,
    character_id: str = DEFAULT_CHARACTER_ID,
    session_id: Optional[str] = None,
) -> None:
    """執行多輪角色一致性檢查。"""

    turns = [
        {
            "intent": "identity_confirmation",
            "text": "您好，請先確認一下您的名字，我怕資料更新錯誤。",
            "notes": "檢查是否自稱為病患。",
        },
        {
            "intent": "room_check",
            "text": "您現在住在幾號病房？",
            "notes": "提醒模型引用既有背景。",
        },
        {
            "intent": "doctor_followup",
            "text": "今天醫師有來巡房嗎？是哪一位？",
            "notes": "確認是否提到合理的醫護角色。",
        },
        {
            "intent": "memory_probe",
            "text": "昨天我們談到頭暈的問題，今天還有持續嗎？",
            "notes": "測試對前述症狀的記憶。",
        },
        {
            "intent": "background_repeat",
            "text": "方便再說一次，您是跟誰一起住院的？",
            "notes": "測試多輪一致性。",
        },
        {
            "intent": "hobby_question",
            "text": "在醫院休息時通常喜歡做什麼放鬆？",
            "notes": "確認扮演患者、回應口吻。",
        },
        {
            "intent": "role_reconfirmation",
            "text": "最後再確認一次，您現在的身份與感受是什麼？",
            "notes": "結尾檢查，避免角色漂移。",
        },
    ]

    with TranscriptRecorder("scenario_role_identity") as recorder:
        recorder.divider("病患角色一致性場景")
        recorder.log(f"Base URL: {base_url}")
        recorder.log(f"Character ID: {character_id}")
        recorder.log()

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

            hits = detect_role_flags(responses)
            for i, text in enumerate(responses, start=1):
                recorder.log(f"    回應[{i}]: {text}")

            if any(hits.values()):
                recorder.log(
                    f"⚠️ 角色風險: self_intro={len(hits['self_intro'])}, "
                    f"role_drift={len(hits['role_drift'])}, fallback={len(hits['fallback'])}"
                )
                if hits["role_drift"]:
                    recorder.log(f"    角色偏移例句: {hits['role_drift'][:2]}")
                if hits["self_intro"]:
                    recorder.log(f"    自我介紹例句: {hits['self_intro'][:2]}")
                if hits["fallback"]:
                    recorder.log(f"    Fallback 例句: {hits['fallback'][:2]}")
            else:
                recorder.log("✅ 角色設定未見異常")

            recorder.log()

        recorder.log("📊 場景執行完成，請檢視上方 transcript 判斷角色一致性。")


if __name__ == "__main__":
    run_scenario()
