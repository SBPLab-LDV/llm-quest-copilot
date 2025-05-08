from dataclasses import dataclass
from typing import Dict, Any, Optional
import logging

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
        logger = logging.getLogger("character")
        
        logger.debug(f"嘗試從配置創建角色，數據類型: {type(character_data)}")
        logger.debug(f"配置內容: {character_data}")
        
        for key, value in character_data.items():
            logger.debug(f"配置項: {key} = {value} (類型: {type(value)})")
        
        # 創建標準化的參數字典
        params = {
            "name": character_data.get('name'),
            "persona": character_data.get('persona'),
            "backstory": character_data.get('backstory'),
            "goal": character_data.get('goal'),
            "details": character_data.get('details')
        }
        
        logger.debug(f"標準化參數: {params}")
        
        try:
            return cls(
                name=params["name"],
                persona=params["persona"],
                backstory=params["backstory"],
                goal=params["goal"],
                details=params["details"]
            )
        except Exception as e:
            logger.error(f"創建角色失敗: {e}", exc_info=True)
            raise 