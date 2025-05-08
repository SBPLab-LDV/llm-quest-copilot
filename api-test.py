import requests
import json

# 樣本角色配置，用於測試動態配置功能
sample_character_config = {
    "name": "Dynamic Test Patient",
    "persona": "70歲測試男性，用於API動態加載",
    "backstory": "這是一個通過API傳遞的角色配置，用於測試。右下齒齦鱗狀細胞癌，pT2N0M0, stage II。",
    "goal": "成功響應並確認動態配置已生效。",
    "details": {
        "fixed_settings": {
            "流水編號": "DYN001",
            "年齡": 70,
            "性別": "男",
            "診斷": "API測試症",
            "分期": "pT2N0M0, stage II",
            "腫瘤方向": "右側",
            "手術術式": "腫瘤切除+皮瓣重建"
        },
        "floating_settings": {
            "目前接受治療場所": "API測試環境",
            "目前治療階段": "手術後/出院前",
            "目前治療狀態": "腫瘤切除術後，尚未進行化學治療與放射線置離療",
            "腫瘤復發": "無",
            "身高": 175,
            "體重": 70,
            "BMI": 22.9,
            "慢性病": "高血壓",
            "用藥史": "降壓藥",
            "關鍵字": "動態配置",
            "個案現況": "這是一個通過API動態配置的測試角色"
        }
    }
}

# 文本對話 (獲取文本回覆)
def text_dialogue(text, character_id, session_id=None, character_config_payload=None):
    url = "http://120.126.51.6:8000/api/dialogue/text"
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "text"  # 明確指定文本回覆
    }
    # 如果提供了角色配置，加入請求數據
    if character_config_payload:
        data["character_config"] = character_config_payload
    
    response = requests.post(url, json=data)
    return response.json()

# 文本對話 (獲取音頻回覆)
def text_dialogue_with_audio(text, character_id, session_id=None, character_config_payload=None):
    url = "http://120.126.51.6:8000/api/dialogue/text"
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "audio"  # 請求音頻回覆
    }
    # 如果提供了角色配置，加入請求數據
    if character_config_payload:
        data["character_config"] = character_config_payload
    
    response = requests.post(url, json=data)
    
    # 檢查回應類型
    if response.headers.get('Content-Type') == 'audio/wav':
        # 從頭部獲取會話ID
        session_id = response.headers.get('X-Session-ID')
        
        # 保存音頻
        audio_filename = f"response_{hash(text)}.wav"
        with open(audio_filename, "wb") as f:
            f.write(response.content)
            
        return {
            "status": "success",
            "audio_file": audio_filename,
            "session_id": session_id
        }
    else:
        # 如果不是音頻回應，可能是錯誤
        return response.json()

# 音頻對話 (獲取文本回覆)
def audio_dialogue(audio_file_path, character_id, session_id=None, response_format="text"):
    url = "http://120.126.51.6:8000/api/dialogue/audio"
    
    with open(audio_file_path, "rb") as audio_file:
        files = {"audio_file": audio_file}
        data = {
            "character_id": character_id,
            "response_format": response_format
        }
        
        if session_id:
            data["session_id"] = session_id
            
        response = requests.post(url, files=files, data=data)
        
        # 如果請求音頻回覆
        if response_format == "audio" and response.headers.get('Content-Type') == 'audio/wav':
            # 從頭部獲取會話ID
            session_id = response.headers.get('X-Session-ID')
            
            # 保存音頻
            audio_filename = f"response_audio_{hash(audio_file_path)}.wav"
            with open(audio_filename, "wb") as f:
                f.write(response.content)
                
            return {
                "status": "success",
                "audio_file": audio_filename,
                "session_id": session_id
            }
        else:
            # 文本回覆或錯誤
            return response.json()

# 測試現有角色
print("\n--- 測試使用現有角色 ---")
text_result = text_dialogue("您今天感覺如何?", "1")
session_id = text_result["session_id"]
print(f"病患回應: {text_result['responses'][0]}")

# 測試使用動態配置的角色
print("\n--- 測試使用動態配置角色 ---")
dynamic_result = text_dialogue("您好，請介紹一下您的情況", "dynamic_patient", character_config_payload=sample_character_config)
dynamic_session_id = dynamic_result["session_id"]
print(f"動態角色回應: {dynamic_result['responses'][0]}")

# 與動態角色繼續對話
dynamic_followup_result = text_dialogue("您是從哪裡來的?", "dynamic_patient", dynamic_session_id)
print(f"動態角色後續回應: {dynamic_followup_result['responses'][0]}")

# 原有的音頻相關測試 (保留但註釋掉，以便選擇性執行)
'''
# 使用示例: 文本輸入，音頻回覆
audio_response = text_dialogue_with_audio("請說說您的傷口狀況", "1", session_id)
if "audio_file" in audio_response:
    print(f"音頻回覆已保存至: {audio_response['audio_file']}")
    session_id = audio_response["session_id"]

# 使用示例: 音頻輸入，文本回覆
audio_text_result = audio_dialogue("recording.wav", "1", session_id)
print(f"病患回應: {audio_text_result['responses'][0]}")

# 使用示例: 音頻輸入，音頻回覆
audio_audio_result = audio_dialogue("recording.wav", "1", session_id, response_format="audio")
if "audio_file" in audio_audio_result:
    print(f"音頻回覆已保存至: {audio_audio_result['audio_file']}")
'''