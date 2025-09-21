import os
import yaml
from typing import Dict, Any
from ..core.character import Character

def load_config() -> Dict[str, Any]:
    """讀取設定檔"""
    try:
        with open('config/config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file) or {}
    except FileNotFoundError:
        config = {}

    if 'input_mode' not in config:
        config['input_mode'] = 'text'
    if 'voice_input_duration' not in config:
        config['voice_input_duration'] = 5
    if 'google_api_key' not in config or not config['google_api_key']:
        config['google_api_key'] = os.getenv('GOOGLE_API_KEY')
        if not config['google_api_key']:
            raise ValueError("找不到 Google API Key")

    logging_defaults = {
        'llm_raw': False,
        'max_chars': 8000,
        'audio_log_b64': False,
    }
    config.setdefault('logging', {})
    for key, value in logging_defaults.items():
        config['logging'].setdefault(key, value)

    audio_defaults = {
        'use_context': False,
        'prompt_via_dspy': True,
        'consistency_reorder': False,
        'use_option_selector': False,
        'evaluate_only': False,
        'option_count': 4,
    }
    config.setdefault('audio', {})
    for key, value in audio_defaults.items():
        config['audio'].setdefault(key, value)

    config['audio'].setdefault('dspy', {})
    for key, value in {'normalize': False, 'evaluate_only': False, 'auto_select': False}.items():
        config['audio']['dspy'].setdefault(key, value)

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
