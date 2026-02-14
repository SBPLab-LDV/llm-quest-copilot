from __future__ import annotations

import datetime
import json
import logging
import os
from typing import List, Optional, Union

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
        return self.conversation_history[-max_entries:]

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
