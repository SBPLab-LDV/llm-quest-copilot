#!/usr/bin/env python3
"""Regression check for selection-based context management."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import requests


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
CHARACTER_ID = os.getenv("CHARACTER_ID", "1")
TEST_INPUT = os.getenv("TEST_INPUT", "你今天喉嚨還會痛嗎？")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(
        f"{BASE_URL}{path}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def _get_json(path: str) -> Dict[str, Any]:
    response = requests.get(f"{BASE_URL}{path}", timeout=60)
    response.raise_for_status()
    return response.json()


def _check_history(history: List[str], selected_response: str) -> None:
    _assert(len(history) == 2, f"expected 2 confirmed turns, got {len(history)}")
    _assert(history[0].startswith("對話方: "), f"unexpected first turn: {history[0]}")
    _assert(history[1].endswith(selected_response), "patient committed response missing from history")


def main() -> int:
    text_result = _post_json(
        "/api/dialogue/text",
        {
            "text": TEST_INPUT,
            "character_id": CHARACTER_ID,
            "response_format": "text",
        },
    )

    responses = text_result.get("responses") or []
    session_id = text_result.get("session_id")
    selection_required = text_result.get("selection_required")

    _assert(text_result.get("status") == "success", "text endpoint did not return success")
    _assert(session_id, "text endpoint did not return session_id")
    _assert(len(responses) == 4, f"expected 4 candidate responses, got {len(responses)}")
    _assert(selection_required is True, "selection_required should be true for /text")
    _assert(text_result.get("interaction_mode") == "response_selection", "unexpected interaction_mode")
    _assert(text_result.get("selection_kind") == "patient_response", "unexpected selection_kind")

    selected_response = responses[0]
    select_result = _post_json(
        "/api/dialogue/select_response",
        {
            "session_id": session_id,
            "selected_response": selected_response,
        },
    )

    _assert(select_result.get("status") == "success", "select_response did not return success")
    _assert(select_result.get("selection_committed") is True, "selection was not marked committed")
    _assert(select_result.get("interaction_mode") == "selection_committed", "unexpected select interaction_mode")
    _assert(select_result.get("committed_response") == selected_response, "committed response mismatch")
    _assert(select_result.get("selection_source") == "candidate", "selection_source should be candidate")
    _assert(select_result.get("responses") == ["已記錄您的選擇"], "select_response should only acknowledge commit")

    history_result = _get_json(f"/api/dev/session/{session_id}/history")
    conversation_history = history_result.get("conversation_history") or []
    structured_history = history_result.get("structured_history") or []

    _check_history(conversation_history, selected_response)
    _assert(len(structured_history) == 2, f"expected 2 structured turns, got {len(structured_history)}")
    _assert(history_result.get("pending_turn") is None, "pending_turn should be cleared after commit")

    print("selection_commit_flow: PASS")
    print(f"session_id={session_id}")
    print(f"selected_response={selected_response}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"selection_commit_flow: FAIL: {exc}", file=sys.stderr)
        raise
