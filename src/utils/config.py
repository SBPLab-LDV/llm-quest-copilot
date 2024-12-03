import os
import yaml
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """讀取設定檔"""
    try:
        with open('config/config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        config = {'google_api_key': os.getenv('GOOGLE_API_KEY')}
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