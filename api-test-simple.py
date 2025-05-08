"""簡化版測試腳本，專注於測試 API 的動態角色配置功能"""
import requests
import json
import time

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

def test_create_session_with_character_config():
    """測試使用客戶端提供的角色配置創建會話"""
    print("測試使用客戶端提供的角色配置創建會話...")
    
    # 創建自定義角色配置
    character_config = {
        "name": "Test Patient",
        "persona": "測試角色",
        "backstory": "這是一個用於測試的角色。",
        "goal": "測試 DialogueManager 的創建",
        "details": {
            "fixed_settings": {
                "流水編號": 99,
                "年齡": 50,
                "性別": "男"
            },
            "floating_settings": {
                "關鍵字": "測試"
            }
        }
    }
    
    # 發送請求
    response = requests.post(
        API_URL,
        json={
            "text": "您好，這是測試訊息",
            "character_id": "simple_test",
            "session_id": None,
            "response_format": "text",
            "character_config": character_config
        }
    )
    
    # 檢查回應
    if response.status_code == 200:
        print("成功創建會話！")
        print(f"回應: {response.json()}")
        session_id = response.json().get('session_id')
        print(f"會話 ID: {session_id}")
        return session_id
    else:
        print(f"錯誤: {response.status_code} - {response.text}")
        return None

def test_continue_session(session_id):
    """測試使用已創建的會話 ID 繼續對話"""
    print("\n測試繼續會話...")
    
    # 發送請求
    response = requests.post(
        API_URL,
        json={
            "text": "這是後續測試訊息",
            "character_id": "simple_test",
            "session_id": session_id,
            "response_format": "text"
        }
    )
    
    # 檢查回應
    if response.status_code == 200:
        print("成功繼續會話！")
        print(f"回應: {response.json()}")
    else:
        print(f"錯誤: {response.status_code} - {response.text}")

def test_dynamic_patient():
    """測試與動態創建的病患角色對話"""
    print("\n測試與動態創建的病患角色對話...")
    
    # 發送請求
    response = requests.post(
        API_URL,
        json={
            "text": "您好，請介紹一下您的情況",
            "character_id": "dynamic_patient",
            "session_id": None,
            "response_format": "text"
        }
    )
    
    # 檢查回應
    if response.status_code == 200:
        print("成功創建動態病患會話！")
        print(f"回應: {response.json()}")
        session_id = response.json().get('session_id')
        print(f"會話 ID: {session_id}")
        
        # 繼續對話
        time.sleep(2)
        response = requests.post(
            API_URL,
            json={
                "text": "您是從哪裡來的?",
                "character_id": "dynamic_patient",
                "session_id": session_id,
                "response_format": "text"
            }
        )
        
        if response.status_code == 200:
            print("成功繼續動態病患會話！")
            print(f"回應: {response.json()}")
        else:
            print(f"錯誤: {response.status_code} - {response.text}")
    else:
        print(f"錯誤: {response.status_code} - {response.text}")

if __name__ == "__main__":
    # 執行測試
    session_id = test_create_session_with_character_config()
    if session_id:
        time.sleep(2)  # 等待 2 秒
        test_continue_session(session_id)
    
    # 測試動態病患
    test_dynamic_patient() 