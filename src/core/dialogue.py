from __future__ import annotations

import datetime
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Union

from .character import Character
from .state import DialogueState


class DialogueManager:
    """Minimal dialogue manager base class.

    The legacy non-DSPy implementation has been removed. Concrete managers
    (e.g. OptimizedDialogueManagerDSPy) should implement `process_turn`.
    """

    def __init__(
        self,
        character: Character,
        use_terminal: bool = False,
        log_dir: str = "logs",
        log_file_basename: Optional[str] = None,
    ):
        self.character = character
        self.current_state = DialogueState.NORMAL
        self.conversation_history: List[str] = []
        self.structured_history: List[Dict[str, Any]] = []
        self.pending_turn: Optional[Dict[str, Any]] = None
        self.use_terminal = use_terminal
        self.interaction_log: List[dict] = []
        self.log_dir = log_dir

        os.makedirs(self.log_dir, exist_ok=True)

        if log_file_basename:
            mode = "terminal" if self.use_terminal else "gui"
            self.log_filename = f"{log_file_basename}_chat_{mode}.log"
        else:
            today_date_str = datetime.datetime.now().strftime("%Y%m%d")
            mode = "terminal" if self.use_terminal else "gui"
            self.log_filename = f"{today_date_str}_patient_{self.character.name}_chat_{mode}.log"

        self.log_filepath = os.path.join(self.log_dir, self.log_filename)
        self.logger = logging.getLogger(__name__)

    def _format_conversation_history(self) -> List[str]:
        max_entries = 20
        try:
            from .dspy.config import get_config

            dspy_cfg = get_config().get_dspy_config()
            max_entries = int(dspy_cfg.get("max_history_entries", 20) or 20)
        except Exception:
            max_entries = 20
        self._sync_structured_history_from_legacy()
        if self.structured_history:
            rendered = [self._render_legacy_line(turn) for turn in self.structured_history]
            return rendered[-max_entries:]
        return self.conversation_history[-max_entries:]

    def _speaker_label(self, speaker_role: str, speaker_name: Optional[str] = None) -> str:
        if speaker_role == "patient":
            return speaker_name or getattr(self.character, "name", "病患")
        if speaker_role == "clinician":
            return speaker_name or "醫護人員"
        if speaker_role == "caregiver":
            return speaker_name or "對話方"
        return speaker_name or "對話方"

    def _render_legacy_line(self, turn: Dict[str, Any]) -> str:
        speaker_role = str(turn.get("speaker_role") or "caregiver")
        speaker_name = turn.get("speaker_name")
        text = str(turn.get("text") or "").strip()
        label = self._speaker_label(speaker_role, speaker_name)
        return f"{label}: {text}" if text else label

    def _parse_legacy_line(self, line: str) -> Dict[str, Any]:
        raw_line = str(line or "").strip()
        if not raw_line:
            return {
                "turn_id": str(uuid.uuid4()),
                "speaker_role": "system",
                "speaker_name": "系統",
                "text": "",
                "turn_type": "legacy_import",
                "created_at": datetime.datetime.now().isoformat(),
                "metadata": {"legacy_imported": True},
            }

        speaker_name = "對話方"
        speaker_role = "caregiver"
        text = raw_line

        if ": " in raw_line:
            candidate_name, candidate_text = raw_line.split(": ", 1)
            normalized_name = candidate_name.strip()
            speaker_name = normalized_name or speaker_name
            text = candidate_text.strip()

            if normalized_name in {"對話方", "對話方(重述)"}:
                speaker_role = "caregiver"
            elif normalized_name in {"醫護人員"}:
                speaker_role = "clinician"
            elif normalized_name in {"系統"}:
                speaker_role = "system"
            else:
                speaker_role = "patient"
        elif raw_line.startswith("(") and raw_line.endswith(")"):
            speaker_name = "系統"
            speaker_role = "system"

        return {
            "turn_id": str(uuid.uuid4()),
            "speaker_role": speaker_role,
            "speaker_name": speaker_name,
            "text": text,
            "turn_type": "legacy_import",
            "created_at": datetime.datetime.now().isoformat(),
            "metadata": {"legacy_imported": True},
        }

    def _sync_structured_history_from_legacy(self) -> None:
        legacy_len = len(self.conversation_history)
        structured_len = len(self.structured_history)
        if legacy_len <= structured_len:
            return

        for line in self.conversation_history[structured_len:]:
            self.structured_history.append(self._parse_legacy_line(line))

    def _rebuild_conversation_history(self) -> None:
        self.conversation_history = [self._render_legacy_line(turn) for turn in self.structured_history]

    def append_confirmed_turn(
        self,
        *,
        speaker_role: str,
        text: str,
        speaker_name: Optional[str] = None,
        turn_type: str = "confirmed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return None

        self._sync_structured_history_from_legacy()
        turn = {
            "turn_id": str(uuid.uuid4()),
            "speaker_role": speaker_role,
            "speaker_name": speaker_name or self._speaker_label(speaker_role, speaker_name),
            "text": normalized_text,
            "turn_type": turn_type,
            "created_at": datetime.datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self.structured_history.append(turn)
        self.conversation_history.append(self._render_legacy_line(turn))
        return turn

    def replace_last_confirmed_turn(
        self,
        *,
        speaker_role: Optional[str] = None,
        text: str,
        speaker_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return None

        self._sync_structured_history_from_legacy()
        for idx in range(len(self.structured_history) - 1, -1, -1):
            turn = self.structured_history[idx]
            if speaker_role and turn.get("speaker_role") != speaker_role:
                continue
            turn["text"] = normalized_text
            if speaker_name:
                turn["speaker_name"] = speaker_name
            self._rebuild_conversation_history()
            return turn
        return None

    def get_structured_history(self) -> List[Dict[str, Any]]:
        self._sync_structured_history_from_legacy()
        return list(self.structured_history)

    def set_pending_turn(
        self,
        *,
        selection_kind: str,
        candidate_options: List[str],
        dialogue_context: str = "",
        state: str = "NORMAL",
        speaker_role: str = "patient",
        source_text: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_options = [str(option).strip() for option in candidate_options if str(option).strip()]
        pending_turn = {
            "pending_turn_id": str(uuid.uuid4()),
            "selection_kind": selection_kind,
            "speaker_role": speaker_role,
            "source_text": str(source_text or "").strip(),
            "candidate_options": normalized_options,
            "dialogue_context": str(dialogue_context or ""),
            "state": str(state or "NORMAL"),
            "metadata": metadata or {},
            "created_at": datetime.datetime.now().isoformat(),
        }
        self.pending_turn = pending_turn
        return pending_turn

    def get_pending_turn(self) -> Optional[Dict[str, Any]]:
        if self.pending_turn is None:
            return None
        return dict(self.pending_turn)

    def clear_pending_turn(self) -> None:
        self.pending_turn = None

    def commit_pending_turn(self, selected_response: str) -> Dict[str, Any]:
        pending_turn = self.pending_turn
        if pending_turn is None:
            raise ValueError("No pending turn to commit")

        normalized_response = str(selected_response or "").strip()
        if not normalized_response:
            raise ValueError("Selected response is empty")

        candidate_options = pending_turn.get("candidate_options") or []
        if normalized_response not in candidate_options:
            raise ValueError("Selected response does not match current candidate options")

        committed_turn = self.append_confirmed_turn(
            speaker_role=str(pending_turn.get("speaker_role") or "patient"),
            speaker_name=self._speaker_label(
                str(pending_turn.get("speaker_role") or "patient"),
                pending_turn.get("metadata", {}).get("speaker_name"),
            ),
            text=normalized_response,
            turn_type=str(pending_turn.get("selection_kind") or "confirmed"),
            metadata={
                "source_text": pending_turn.get("source_text", ""),
                "selection_kind": pending_turn.get("selection_kind", ""),
                **(pending_turn.get("metadata") or {}),
            },
        )
        self.clear_pending_turn()
        if committed_turn is None:
            raise ValueError("Failed to commit pending turn")
        return committed_turn

    def log_interaction(
        self,
        user_input: str,
        response_options: list,
        selected_response: Optional[str] = None,
        raw_transcript: Optional[str] = None,
        keyword_completion: Optional[list] = None,
    ):
        timestamp = datetime.datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "user_input": user_input,
            "response_options": response_options,
            "selected_response": selected_response,
            "raw_transcript": raw_transcript,
            "keyword_completion": keyword_completion,
        }
        self.interaction_log.append(log_entry)

    def save_interaction_log(self):
        if not self.interaction_log:
            return

        try:
            with open(self.log_filepath, "a", encoding="utf-8") as file:
                for entry in self.interaction_log:
                    json.dump(entry, file, ensure_ascii=False)
                    file.write("\n")
            self.interaction_log = []
        except Exception:
            self.logger.exception("Failed to save interaction log: %s", self.log_filepath)

    async def process_turn(self, user_input: str, gui_selected_response: Optional[str] = None) -> Union[str, dict]:
        raise NotImplementedError("DialogueManager.process_turn must be implemented by subclasses.")

    def cleanup(self):
        self.save_interaction_log()
