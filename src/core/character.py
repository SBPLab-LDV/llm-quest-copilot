from dataclasses import dataclass

@dataclass
class Character:
    """角色基本資訊"""
    name: str
    persona: str
    backstory: str
    goal: str 