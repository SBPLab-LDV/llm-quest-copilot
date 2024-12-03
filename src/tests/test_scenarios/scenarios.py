from typing import List, Dict
import yaml

def load_test_scenarios() -> List[Dict]:
    """讀取測試情境"""
    with open('config/test_scenarios.yaml', 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
        return data['scenarios'] 