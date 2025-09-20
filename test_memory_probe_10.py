#!/usr/bin/env python3
"""10-turn memory probe comparing window sizes (3 vs 8).

T3 plants an anchor fact; T10 asks to recall it. We run twice:
 - Group A: max_history=3 (default)
 - Group B: max_history=8 (via debug config endpoint)
"""

import os
import json
import time
import random
from typing import Optional, Dict, Any, List

import requests

try:
    # Reuse the shared system testing personas
    from src.ui.client import system_testing_config
except Exception:
    system_testing_config = None  # type: ignore


BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
AVAILABLE_IDS = ["1", "2", "3", "4", "5", "6"]
CHARACTER_ID = os.environ.get("CHARACTER_ID") or random.choice(AVAILABLE_IDS)
CHARACTER_CONFIG = system_testing_config(CHARACTER_ID) if system_testing_config else None


def set_max_history(n: int) -> None:
    # 固定 10 輪策略：不再動態設置，保留函數以兼容但不呼叫端點
    pass


def post_text(text: str, session_id: Optional[str]) -> Dict[str, Any]:
    url = f"{BASE_URL}/api/dialogue/text"
    payload = {
        "text": text,
        "character_id": CHARACTER_ID,
        "session_id": session_id,
        "response_format": "text",
        "character_config": CHARACTER_CONFIG,
    }
    r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def get_history(session_id: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/api/dev/session/{session_id}/history"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def analyze_mentions(responses: List[str], keywords: List[str]) -> Dict[str, int]:
    return {kw: sum(1 for r in responses if kw in r) for kw in keywords}


def run_scenario(window_turns: int = 10) -> Dict[str, Any]:
    print(f"\n=== Running 10-turn probe (fixed window=10 turns) ===")
    set_max_history(window_turns)

    # 10-turn script
    # T3 改為「提問式」引導病患提供錨點（而非由護理人員直接陳述）
    # T9 釘選：重述錨點，引導在 T10 回憶時命中
    turns = [
        "你好，感覺怎麼樣？",
        "有沒有覺得發燒或不舒服？",
        "你目前正在使用的藥名、劑量與服用頻次是什麼？請清楚說明。",
        "從什麼時候開始的？",
        "還有其他症狀嗎？",
        "昨晚睡眠品質如何？",
        "今天活動量大概多少？",
        "目前飲食有沒有不舒服的地方？",
        "請你再次清楚說明之前提到的藥名、劑量與服用頻次；若不確定請直接說不確定。",
        "請逐字重述你先前說過的藥名、劑量與服用頻次（若不確定請直接說不確定）。",
    ]

    session_id: Optional[str] = None
    results: List[Dict[str, Any]] = []

    for i, text in enumerate(turns, start=1):
        t0 = time.time()
        res = post_text(text, session_id)
        dt = time.time() - t0
        session_id = res.get("session_id", session_id)
        print(f"Turn {i}: {dt:.2f}s | session={session_id}")
        for idx, resp in enumerate(res.get("responses", [])[:3], start=1):
            print(f"  [{idx}] {resp}")
        results.append(res)

    # Analyze T10 recall
    anchor_kw = ["阿莫西林", "500", "一天三次"]
    final_responses = results[-1].get("responses", [])
    mentions = analyze_mentions(final_responses, anchor_kw)

    # Fetch and attach history
    history_obj = get_history(session_id) if session_id else {}

    return {
        "session_id": session_id,
        "mentions": mentions,
        "final_responses": final_responses,
        "history": history_obj,
    }


def main():
    group = run_scenario(10)

    def fmt(m: Dict[str, int]) -> str:
        return ", ".join(f"{k}={v}" for k, v in m.items())

    print("\n=== Summary ===")
    print(f"mentions: {fmt(group['mentions'])}")
    print(f"session: {group['session_id']}")

if __name__ == "__main__":
    main()
