import os
import yaml
from typing import Dict, Any
from ..core.character import Character

def load_config() -> Dict[str, Any]:
    """讀取設定檔"""
    try:
        with open('config/config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            # 設定預設值
            if 'input_mode' not in config:
                config['input_mode'] = 'text'
            if 'voice_input_duration' not in config:
                config['voice_input_duration'] = 5
    except FileNotFoundError:
        config = {
            'google_api_key': os.getenv('GOOGLE_API_KEY'),
            'input_mode': 'text',
            'voice_input_duration': 5
        }
        if not config['google_api_key']:
            raise ValueError("找不到 Google API Key")
    return config

def load_prompts() -> Dict[str, str]:
    """讀取提示詞"""
    try:
        with open('prompts/dialogue_prompts.yaml', 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError("找不到提示詞檔案")

def load_character(character_id: str) -> Character:
    """讀取特定角色設定"""
    try:
        with open('config/characters.yaml', 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            if character_id not in data['characters']:
                raise ValueError(f"找不到角色 ID: {character_id}")

            char_data = data['characters'][character_id]
            # 使用 Character.from_yaml class method 來建立 Character 物件
            return Character.from_yaml(char_data)

    except FileNotFoundError:
        raise FileNotFoundError("找不到角色設定檔")

def list_available_characters() -> Dict[str, Dict[str, str]]:
    """列出所有可用的角色"""
    try:
        with open('config/characters.yaml', 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            return data['characters']
    except FileNotFoundError:
        raise FileNotFoundError("找不到角色設定檔") 