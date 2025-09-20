from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import random

DEFAULT_BASE_URL = "http://localhost:8000"

# Available test characters (aligned with src/ui/client.py system_testing_config)
AVAILABLE_TEST_CHARACTER_IDS: List[str] = ["1", "2", "3", "4", "5", "6"]

# Randomly choose one persona per test run
DEFAULT_CHARACTER_ID = random.choice(AVAILABLE_TEST_CHARACTER_IDS)

def get_character_config(character_id: str):
    """Return the structured character_config for the given id.

    Uses src.ui.client.system_testing_config as the single source of truth so
    tests and UI share identical persona definitions.
    """
    try:
        from src.ui.client import system_testing_config  # lazy import
        return system_testing_config(str(character_id))
    except Exception:
        # If anything fails, let server fall back to default Patient_{id}
        return None

SELF_INTRO_PATTERNS = [
    "我是Patient",
    "您好，我是",
    "我是病患",
]

GENERIC_PATTERNS = [
    "我可能沒有完全理解",
    "能請您換個方式說明",
    "您需要什麼幫助嗎",
]

FALLBACK_PATTERNS = [
    "我可能沒有完全理解",
    "能請您換個方式說明",
    "我不太確定",
    "抱歉",
    "請再描述一次",
]


class TranscriptRecorder:
    """Collects stdout so every scenario run has a saved transcript."""

    def __init__(self, scenario_name: str, log_root: Optional[Path] = None) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.scenario_name = scenario_name
        self.log_dir = (log_root or Path("logs") / "dialogue_quality")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{timestamp}_{scenario_name}.log"
        self._lines: List[str] = []

    def log(self, message: str = "") -> None:
        print(message)
        self._lines.append(message)

    def divider(self, label: str = "") -> None:
        bar = "=" * 60
        if label:
            self.log(bar)
            self.log(label)
            self.log(bar)
        else:
            self.log(bar)

    def finalize(self) -> None:
        with self.log_path.open("w", encoding="utf-8") as handle:
            handle.write("\n".join(self._lines))
            if self._lines:
                handle.write("\n")

    def __enter__(self) -> "TranscriptRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.finalize()
