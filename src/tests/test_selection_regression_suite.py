#!/usr/bin/env python3
"""Regression suite for selection-based dialogue context management."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import requests


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
CHARACTER_ID = os.getenv("CHARACTER_ID", "1")
TEXT_FIXTURE = os.getenv("TEXT_FIXTURE", "你今天喉嚨還會痛嗎？")
TEXT_FIXTURE_2 = os.getenv("TEXT_FIXTURE_2", "現在食慾怎麼樣？")
AUDIO_FIXTURE = os.getenv("AUDIO_FIXTURE", "/app/recording.wav")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _post_json(path: str, payload: Dict[str, Any], expected_status: int = 200) -> requests.Response:
    response = requests.post(
        f"{BASE_URL}{path}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    _assert(
        response.status_code == expected_status,
        f"{path} returned {response.status_code}, expected {expected_status}: {response.text}",
    )
    return response


def _post_audio(path: str, *, session_id: str | None = None, expected_status: int = 200) -> requests.Response:
    data = {"character_id": CHARACTER_ID}
    if session_id:
        data["session_id"] = session_id
    with open(AUDIO_FIXTURE, "rb") as audio_fp:
        response = requests.post(
            f"{BASE_URL}{path}",
            files={"audio_file": (os.path.basename(AUDIO_FIXTURE), audio_fp, "audio/wav")},
            data=data,
            timeout=300,
        )
    _assert(
        response.status_code == expected_status,
        f"{path} returned {response.status_code}, expected {expected_status}: {response.text}",
    )
    return response


def _get_json(path: str, expected_status: int = 200) -> requests.Response:
    response = requests.get(f"{BASE_URL}{path}", timeout=60)
    _assert(
        response.status_code == expected_status,
        f"{path} returned {response.status_code}, expected {expected_status}: {response.text}",
    )
    return response


def _select(session_id: str, selected_response: str, expected_status: int = 200) -> Dict[str, Any]:
    response = _post_json(
        "/api/dialogue/select_response",
        {"session_id": session_id, "selected_response": selected_response},
        expected_status=expected_status,
    )
    return response.json()


def _history(session_id: str) -> Dict[str, Any]:
    return _get_json(f"/api/dev/session/{session_id}/history").json()


def _assert_commit_result(result: Dict[str, Any], selected_response: str) -> None:
    _assert(result.get("status") == "success", "selection commit did not return success")
    _assert(result.get("selection_committed") is True, "selection_committed should be true")
    _assert(result.get("interaction_mode") == "selection_committed", "unexpected interaction_mode")
    _assert(result.get("committed_response") == selected_response, "committed response mismatch")
    _assert(result.get("responses") == ["已記錄您的選擇"], "select_response should only acknowledge commit")


def _assert_roles(history_result: Dict[str, Any], expected_roles: List[str]) -> None:
    structured_history = history_result.get("structured_history") or []
    actual_roles = [turn.get("speaker_role") for turn in structured_history]
    _assert(
        actual_roles == expected_roles,
        f"unexpected speaker_role sequence: {actual_roles}, expected {expected_roles}",
    )


def test_audio_input_selection_commit_flow() -> None:
    response = _post_audio("/api/dialogue/audio_input").json()
    responses = response.get("responses") or []
    session_id = response.get("session_id")

    _assert(response.get("status") == "success", "audio_input did not return success")
    _assert(session_id, "audio_input did not return session_id")
    _assert(response.get("selection_required") is True, "audio_input should require selection")
    _assert(response.get("interaction_mode") == "response_selection", "audio_input mode mismatch")
    _assert(response.get("selection_kind") == "patient_response", "audio_input selection kind mismatch")
    _assert(len(responses) == 4, f"audio_input should return 4 patient candidates, got {len(responses)}")
    _assert(bool(response.get("original_transcription")), "audio_input should return original_transcription")

    selected_response = responses[0]
    _assert_commit_result(_select(session_id, selected_response), selected_response)

    history_result = _history(session_id)
    conversation_history = history_result.get("conversation_history") or []
    _assert(len(conversation_history) == 2, f"audio_input history should have 2 confirmed turns, got {len(conversation_history)}")
    _assert(conversation_history[0].startswith("對話方: "), f"unexpected caregiver history line: {conversation_history[0]}")
    _assert(response["original_transcription"] in conversation_history[0], "transcription should be committed as caregiver turn")
    _assert(conversation_history[1].endswith(selected_response), "selected patient response missing from history")
    _assert_roles(history_result, ["caregiver", "patient"])
    _assert(history_result.get("pending_turn") is None, "pending_turn should be cleared after audio_input commit")


def test_audio_patient_completion_flow() -> None:
    response = _post_audio("/api/dialogue/audio").json()
    session_id = response.get("session_id")
    options = response.get("speech_recognition_options") or []

    _assert(response.get("status") == "success", "audio did not return success")
    _assert(session_id, "audio did not return session_id")
    _assert(response.get("selection_required") is True, "audio should require selection")
    _assert(response.get("interaction_mode") == "response_selection", "audio mode mismatch")
    _assert(response.get("selection_kind") == "patient_utterance_completion", "audio selection kind mismatch")
    _assert(response.get("state") == "WAITING_SELECTION", "audio should remain in WAITING_SELECTION before commit")
    _assert(response.get("responses") == ["請從以下選項中選擇您想表達的內容:"], "audio prompt response mismatch")
    _assert(len(options) >= 1, "audio should return at least one candidate option")

    selected_response = options[0]
    _assert_commit_result(_select(session_id, selected_response), selected_response)

    history_result = _history(session_id)
    conversation_history = history_result.get("conversation_history") or []
    _assert(len(conversation_history) == 1, f"audio completion history should have 1 confirmed turn, got {len(conversation_history)}")
    _assert(conversation_history[0].endswith(selected_response), "selected patient completion missing from history")
    _assert_roles(history_result, ["patient"])
    _assert(history_result.get("pending_turn") is None, "pending_turn should be cleared after audio commit")


def test_mixed_selection_context_flow() -> None:
    text_one = _post_json(
        "/api/dialogue/text",
        {"text": TEXT_FIXTURE, "character_id": CHARACTER_ID, "response_format": "text"},
    ).json()
    session_id = text_one["session_id"]
    _assert_commit_result(_select(session_id, text_one["responses"][0]), text_one["responses"][0])

    audio_input = _post_audio("/api/dialogue/audio_input", session_id=session_id).json()
    _assert(audio_input.get("session_id") == session_id, "audio_input should stay in same session")
    _assert_commit_result(_select(session_id, audio_input["responses"][0]), audio_input["responses"][0])

    audio = _post_audio("/api/dialogue/audio", session_id=session_id).json()
    _assert(audio.get("session_id") == session_id, "audio should stay in same session")
    patient_completion = (audio.get("speech_recognition_options") or [None])[0]
    _assert(bool(patient_completion), "audio should return a selectable patient completion")
    _assert_commit_result(_select(session_id, patient_completion), patient_completion)

    text_two = _post_json(
        "/api/dialogue/text",
        {
            "text": TEXT_FIXTURE_2,
            "character_id": CHARACTER_ID,
            "session_id": session_id,
            "response_format": "text",
        },
    ).json()
    _assert(text_two.get("session_id") == session_id, "second text turn should stay in same session")
    _assert_commit_result(_select(session_id, text_two["responses"][0]), text_two["responses"][0])

    history_result = _history(session_id)
    conversation_history = history_result.get("conversation_history") or []
    _assert(len(conversation_history) == 7, f"mixed flow should have 7 confirmed turns, got {len(conversation_history)}")
    _assert(TEXT_FIXTURE in conversation_history[0], "first caregiver turn missing")
    _assert(audio_input["original_transcription"] in conversation_history[2], "audio_input caregiver transcription missing")
    _assert(TEXT_FIXTURE_2 in conversation_history[5], "second caregiver turn missing")
    _assert_roles(
        history_result,
        ["caregiver", "patient", "caregiver", "patient", "patient", "caregiver", "patient"],
    )
    _assert(history_result.get("pending_turn") is None, "pending_turn should be cleared after mixed flow")


def test_selection_failure_paths() -> None:
    text_result = _post_json(
        "/api/dialogue/text",
        {"text": "你現在有哪裡不舒服？", "character_id": CHARACTER_ID, "response_format": "text"},
    ).json()
    session_id = text_result["session_id"]
    first_options = text_result["responses"]

    invalid_response = _select(session_id, "這不是候選答案", expected_status=400)
    _assert("does not match current candidate options" in invalid_response.get("detail", ""), "invalid selection should be rejected")

    overwrite_result = _post_json(
        "/api/dialogue/text",
        {
            "text": "吞口水會更痛嗎？",
            "character_id": CHARACTER_ID,
            "session_id": session_id,
            "response_format": "text",
        },
    ).json()
    second_options = overwrite_result["responses"]
    _assert(overwrite_result.get("session_id") == session_id, "overwrite scenario should stay in same session")

    old_option_result = _select(session_id, first_options[0], expected_status=400)
    _assert("does not match current candidate options" in old_option_result.get("detail", ""), "stale option should be rejected after overwrite")

    selected_response = second_options[0]
    _assert_commit_result(_select(session_id, selected_response), selected_response)

    no_pending_result = _select(session_id, selected_response, expected_status=409)
    _assert("沒有待確認的病患選項" in no_pending_result.get("detail", ""), "missing pending_turn should return 409")


def main() -> int:
    _assert(os.path.exists(AUDIO_FIXTURE), f"audio fixture not found: {AUDIO_FIXTURE}")

    test_audio_input_selection_commit_flow()
    print("audio_input_selection_commit_flow: PASS")

    test_audio_patient_completion_flow()
    print("audio_patient_completion_flow: PASS")

    test_mixed_selection_context_flow()
    print("mixed_selection_context_flow: PASS")

    test_selection_failure_paths()
    print("selection_failure_paths: PASS")

    print("selection_regression_suite: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"selection_regression_suite: FAIL: {exc}", file=sys.stderr)
        raise
