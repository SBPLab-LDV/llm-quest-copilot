#!/usr/bin/env python3
"""5-turn audio memory probe using assets/01.mp3..05.mp3.

Posts each audio to /api/dialogue/audio_input, preserving session_id.
Prints transcription, options count, and top 3 generated responses.
"""

import requests
import time

BASE_URL = "http://localhost:8000"
CHARACTER_ID = "6"
AUDIO_FILES = [f"assets/0{i}.mp3" for i in range(1, 6)]


def main() -> None:
    session_id = None
    for idx, path in enumerate(AUDIO_FILES, start=1):
        with open(path, "rb") as f:
            data = {"character_id": CHARACTER_ID}
            if session_id:
                data["session_id"] = session_id
            t0 = time.time()
            resp = requests.post(
                f"{BASE_URL}/api/dialogue/audio_input",
                files={"audio_file": f},
                data=data,
                timeout=240,
            )
        dt = time.time() - t0
        try:
            obj = resp.json()
        except Exception:
            print(f"Turn {idx}: HTTP {resp.status_code}\n{resp.text[:500]}")
            return
        session_id = obj.get("session_id", session_id)
        print(f"[#] Turn {idx} | {dt:.2f}s | session={session_id}")
        print("   original:", obj.get("original_transcription"))
        opts = obj.get("speech_recognition_options") or []
        print("   options_len:", len(opts))
        for i, r in enumerate((obj.get("responses") or [])[:3], 1):
            print(f"   [{i}] {r}")

    if session_id:
        h = requests.get(f"{BASE_URL}/api/dev/session/{session_id}/history").json()
        print("\n=== Session Summary ===")
        print("implementation:", h.get("implementation_version"))
        history = h.get("conversation_history") or []
        print("history_lines:", len(history))
        for ln in history[-10:]:
            print("  ", ln)


if __name__ == "__main__":
    main()

