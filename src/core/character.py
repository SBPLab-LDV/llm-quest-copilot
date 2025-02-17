from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Character:
    """病患基本資訊"""
    name: str
    persona: str
    backstory: str
    goal: str
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def from_yaml(cls, character_data: Dict[str, Any]) -> 'Character':
        """從 YAML 資料建立 Character 物件"""
        return cls(
            name=character_data.get('name'),
            persona=character_data.get('persona'),
            backstory=character_data.get('backstory'),
            goal=character_data.get('goal'),
            details=character_data.get('details')
        ) 