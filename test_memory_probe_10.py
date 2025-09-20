#!/usr/bin/env python3
"""10-turn memory probe comparing window sizes (3 vs 8).

T3 plants an anchor fact; T10 asks to recall it. We run twice:
 - Group A: max_history=3 (default)
 - Group B: max_history=8 (via debug config endpoint)
"""

import os
import json
import time
from typing import Optional, Dict, Any, List

import requests


BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
CHARACTER_ID = os.environ.get("CHARACTER_ID", "1")


def set_max_history(n: int) -> None:
    url = f"{BASE_URL}/api/dev/config/set_max_history"
    r = requests.post(url, headers={"Content-Type": "application/json"}, json={"max_history": n}, timeout=10)
    r.raise_for_status()


def post_text(text: str, session_id: Optional[str]) -> Dict[str, Any]:
    url = f"{BASE_URL}/api/dialogue/text"
    payload = {
        "text": text,
        "character_id": CHARACTER_ID,
        "session_id": session_id,
        "response_format": "text",
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


def run_scenario(max_history: int) -> Dict[str, Any]:
    print(f"\n=== Running 10-turn probe with max_history={max_history} ===")
    set_max_history(max_history)

    # 10-turn script
    # T3 plants anchor: 阿莫西林 500mg 一天三次
    turns = [
        "你好，感覺怎麼樣？",
        "有沒有覺得發燒或不舒服？",
        "我昨天開始服用阿莫西林500mg，一天三次，目前疼痛稍微減輕。",
        "從什麼時候開始的？",
        "還有其他症狀嗎？",
        "昨晚睡眠品質如何？",
        "今天活動量大概多少？",
        "目前飲食有沒有不舒服的地方？",
        "需要再加藥或調整劑量嗎？",
        "你第三輪說的藥名、劑量和頻次是什麼？",
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
    groupA = run_scenario(3)
    groupB = run_scenario(8)

    def fmt(m: Dict[str, int]) -> str:
        return ", ".join(f"{k}={v}" for k, v in m.items())

    print("\n=== Comparison Summary ===")
    print(f"A (max_history=3)  mentions: {fmt(groupA['mentions'])}")
    print(f"B (max_history=8)  mentions: {fmt(groupB['mentions'])}")
    
    # Basic judgment: if B mentions more anchors than A, window expansion helped.
    scoreA = sum(groupA['mentions'].values())
    scoreB = sum(groupB['mentions'].values())
    verdict = "IMPROVED" if scoreB > scoreA else ("SAME" if scoreB == scoreA else "WORSE")
    print(f"Verdict: {verdict} (A={scoreA}, B={scoreB})")

    # Output session ids for reference
    print(f"Sessions: A={groupA['session_id']} | B={groupB['session_id']}")

if __name__ == "__main__":
    main()

