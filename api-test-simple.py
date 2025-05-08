"""簡化版測試腳本，專注於測試 API 的動態角色配置功能"""
import requests
import json

# 定義 API 端點
API_URL = "http://localhost:8000/api/dialogue/text"

# 極簡化的角色配置
simple_config = {
    "name": "Minimal Test Patient",
    "persona": "簡單測試角色",
    "backstory": "僅用於測試的最小化角色配置",
    "goal": "測試 API 的動態角色配置功能",
    "details": None  # 設為 None 以減少可能的問題
}

# 發送請求
def send_request(text, character_id, character_config=None, session_id=None):
    """發送一個文本對話請求
    
    Args:
        text: 用戶輸入的文本
        character_id: 角色 ID
        character_config: 角色配置 (可選)
        session_id: 會話 ID (可選)
    
    Returns:
        API 回應
    """
    data = {
        "text": text,
        "character_id": character_id,
        "response_format": "text"
    }
    
    if session_id:
        data["session_id"] = session_id
    
    if character_config:
        data["character_config"] = character_config
    
    print(f"發送請求: {data}")
    response = requests.post(API_URL, json=data)
    
    return response.json()

# 測試動態角色配置
print("--- 測試極簡版角色配置 ---")
response = send_request("你好", "minimal_test", simple_config)
print(f"回應: {response}")

if "session_id" in response:
    session_id = response["session_id"]
    print("成功獲取會話 ID，進行後續對話測試...")
    
    # 後續對話測試
    followup_response = send_request("這是後續對話", "minimal_test", session_id=session_id)
    print(f"後續回應: {followup_response}")
else:
    print("錯誤: 無法獲取會話 ID") 