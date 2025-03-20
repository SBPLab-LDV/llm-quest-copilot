import requests
import json
import os
import wave
import numpy as np
import tempfile
from scipy.io import wavfile
import uuid

# 首先獲取可用角色列表
def get_characters():
    url = "http://localhost:8000/api/characters"
    response = requests.get(url)
    return response.json()["characters"]

# 文本對話 (獲取文本回覆)
def text_dialogue(text, character_id, session_id=None):
    url = "http://localhost:8000/api/dialogue/text"
    headers = {"Content-Type": "application/json"}
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "text"  # 明確指定文本回覆
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 文本對話 (獲取音頻回覆)
def text_dialogue_with_audio(text, character_id, session_id=None):
    url = "http://localhost:8000/api/dialogue/text"
    headers = {"Content-Type": "application/json"}
    data = {
        "text": text,
        "character_id": character_id,
        "session_id": session_id,
        "response_format": "audio"  # 請求音頻回覆
    }
    response = requests.post(url, headers=headers, json=data)
    
    # 檢查回應類型
    if response.headers.get('Content-Type') == 'audio/wav':
        # 生成唯一文件名
        audio_filename = f"response_{uuid.uuid4().hex[:8]}.wav"
        # 保存音頻
        with open(audio_filename, "wb") as f:
            f.write(response.content)
        
        # 從頭部獲取會話ID，如果有的話
        session_id = response.headers.get('X-Session-ID', session_id)
        
        return {
            "status": "success",
            "audio_file": audio_filename,
            "session_id": session_id
        }
    else:
        # 不是音頻回應，可能是錯誤
        try:
            return response.json()
        except:
            return {
                "status": "error",
                "detail": f"預期音頻，但收到未知格式: {response.headers.get('Content-Type')}",
                "content": response.text[:100] + "..."  # 只顯示部分內容
            }

# 音頻對話 (獲取文本回覆)
def audio_dialogue(audio_file_path, character_id, session_id=None):
    url = "http://localhost:8000/api/dialogue/audio"
    
    try:
        with open(audio_file_path, "rb") as audio_file:
            files = {"audio_file": audio_file}
            data = {
                "character_id": character_id,
                "response_format": "text"  # 明確指定文本回覆
            }
            
            if session_id:
                data["session_id"] = session_id
                
            response = requests.post(url, files=files, data=data)
            return response.json()
    except FileNotFoundError:
        print(f"錯誤: 找不到音頻文件 '{audio_file_path}'")
        return {"status": "error", "detail": f"找不到音頻文件 '{audio_file_path}'"}
    except Exception as e:
        print(f"音頻請求出錯: {e}")
        return {"status": "error", "detail": str(e)}

# 音頻對話 (獲取音頻回覆)
def audio_dialogue_with_audio(audio_file_path, character_id, session_id=None):
    url = "http://localhost:8000/api/dialogue/audio"
    
    try:
        with open(audio_file_path, "rb") as audio_file:
            files = {"audio_file": audio_file}
            data = {
                "character_id": character_id,
                "response_format": "audio"  # 請求音頻回覆
            }
            
            if session_id:
                data["session_id"] = session_id
                
            response = requests.post(url, files=files, data=data)
            
            # 檢查回應類型
            if response.headers.get('Content-Type') == 'audio/wav':
                # 生成唯一文件名
                audio_filename = f"response_{uuid.uuid4().hex[:8]}.wav"
                # 保存音頻
                with open(audio_filename, "wb") as f:
                    f.write(response.content)
                
                # 從頭部獲取會話ID，如果有的話
                session_id = response.headers.get('X-Session-ID', session_id)
                
                return {
                    "status": "success",
                    "audio_file": audio_filename,
                    "session_id": session_id
                }
            else:
                # 不是音頻回應，可能是錯誤
                try:
                    return response.json()
                except:
                    return {
                        "status": "error",
                        "detail": f"預期音頻，但收到未知格式: {response.headers.get('Content-Type')}",
                        "content": response.text[:100] + "..."  # 只顯示部分內容
                    }
    except FileNotFoundError:
        print(f"錯誤: 找不到音頻文件 '{audio_file_path}'")
        return {"status": "error", "detail": f"找不到音頻文件 '{audio_file_path}'"}
    except Exception as e:
        print(f"音頻請求出錯: {e}")
        return {"status": "error", "detail": str(e)}


# 獲取可用角色
try:
    characters = get_characters()
    print("可用角色:")
    for char_id, char_info in characters.items():
        print(f"  ID: {char_id}, 名稱: {char_info['name']}")
    
    # 使用第一個可用角色
    first_char_id = list(characters.keys())[0]
    char_id_to_use = first_char_id
except Exception as e:
    print(f"獲取角色列表失敗: {e}")
    print("使用預設角色 ID '1'")
    char_id_to_use = "1"

# 使用示例
print(f"\n開始與角色 ID '{char_id_to_use}' 對話:")

# 測試音頻上傳功能 (獲取文本回覆)
print("\n----- 音頻對話測試（文本回覆）-----")

# 設定音頻檔案列表
audio_files = [
    "recording.wav",            # 默認名稱
    "test_recording.wav",       # 備選名稱
]

# 檢查哪些文件存在
existing_files = []
for file_path in audio_files:
    if os.path.exists(file_path):
        existing_files.append(file_path)
        print(f"找到音頻文件: {file_path}")

# 如果至少有一個音頻文件存在，就進行測試
if existing_files:
    session_id = None  # 初始化會話ID為None
    
    # 按順序測試每個存在的音頻文件
    for i, audio_file in enumerate(existing_files):
        print(f"\n----- 測試第 {i+1}/{len(existing_files)} 個音頻文件: {audio_file} -----")
        
        # 發送音頻請求，獲取文本回覆
        audio_result = audio_dialogue(audio_file, char_id_to_use, session_id)
        print(json.dumps(audio_result, indent=2, ensure_ascii=False))
        
        # 獲取或更新會話ID（用於後續請求）
        if "session_id" in audio_result:
            session_id = audio_result["session_id"]
            print(f"使用會話ID: {session_id}")
        else:
            print("警告: 回應中沒有會話ID，無法繼續測試後續文件")
            break
    
    # 測試音頻回覆功能
    if session_id:
        print("\n----- 測試文本輸入獲取音頻回覆 -----")
        audio_response = text_dialogue_with_audio("我想聽聽您的聲音", char_id_to_use, session_id)
        if "audio_file" in audio_response:
            print(f"音頻回覆已保存至: {audio_response['audio_file']}")
        else:
            print("未能獲取音頻回覆:")
            print(json.dumps(audio_response, indent=2, ensure_ascii=False))
        
        # 如果還有其他音頻文件，繼續測試音頻輸入獲取音頻回覆
        if len(existing_files) > 1:
            print("\n----- 測試音頻輸入獲取音頻回覆 -----")
            another_audio_file = existing_files[1] if i == 0 else existing_files[0]
            audio_audio_response = audio_dialogue_with_audio(another_audio_file, char_id_to_use, session_id)
            if "audio_file" in audio_audio_response:
                print(f"音頻回覆已保存至: {audio_audio_response['audio_file']}")
            else:
                print("未能獲取音頻回覆:")
                print(json.dumps(audio_audio_response, indent=2, ensure_ascii=False))
        
        # 最後用文本繼續對話
        print("\n----- 使用文本完成對話 -----")
        final_text = text_dialogue("謝謝您的配合，我們會安排進一步檢查", char_id_to_use, session_id)
        print(json.dumps(final_text, indent=2, ensure_ascii=False))
else:
    print("無法進行音頻測試：未找到任何音頻文件")
    print("請確保以下文件至少存在一個:")
    for file in audio_files:
        print(f"  - {file}")