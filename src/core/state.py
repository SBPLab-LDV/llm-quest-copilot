from enum import Enum

class DialogueState(Enum):
    """對話狀態列舉"""
    NORMAL = "NORMAL"
    TRANSITIONING = "TRANSITIONING"
    CONFUSED = "CONFUSED"
    TERMINATED = "TERMINATED" 