#!/usr/bin/env python3
"""Quick probe for numeric diversity and patient voice.

Sends a single question about IV bag count to the dialogue API
and prints the responses to inspect slot diversity and tone.
"""

import os
import json
import random
from typing import Optional, Dict, Any

import requests

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
AVAILABLE_IDS = ["1", "2", "3", "4", "5", "6"]
CHARACTER_ID = os.environ.get("CHARACTER_ID") or random.choice(AVAILABLE_IDS)

try:
    from src.ui.client import system_testing_config
except Exception:
    system_testing_config = None  # type: ignore

CHARACTER_CONFIG = system_testing_config(CHARACTER_ID) if system_testing_config else None


def post_text(text: str, session_id: Optional[str] = None) -> Dict[str, Any]:
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


def main():
    question = "今天早上打了幾罐點滴？"
    print(f"Probing: {question}")
    res = post_text(question, None)
    print(f"session: {res.get('session_id')}")
    print("Responses:")
    for i, s in enumerate(res.get("responses", []), start=1):
        print(f"  [{i}] {s}")


if __name__ == "__main__":
    main()

