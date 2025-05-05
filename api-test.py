import requests
import json

# 文本對話 (獲取文本回覆)
def text_dialogue(text, character_id, session_id=None):
    url = "http://120.126.51.6:8000/api/dialogue/text"
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "text"  # 明確指定文本回覆
    }
    response = requests.post(url, json=data)
    return response.json()

# 文本對話 (獲取音頻回覆)
def text_dialogue_with_audio(text, character_id, session_id=None):
    url = "http://120.126.51.6:8000/api/dialogue/text"
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "audio"  # 請求音頻回覆
    }
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

# 使用示例: 文本輸入，文本回覆
text_result = text_dialogue("您今天感覺如何?", "1")
session_id = text_result["session_id"]
print(f"病患回應: {text_result['responses'][0]}")

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
    # 可以播放音頻或進行其他處理