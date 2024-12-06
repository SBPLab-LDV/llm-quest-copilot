from dataclasses import dataclass

@dataclass
class Character:
    """病患基本資訊"""
    name: str
    persona: str
    backstory: str
    goal: str 