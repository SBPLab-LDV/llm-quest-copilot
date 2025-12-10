"""
測試 dialogue API 使用 M4A 音檔
基於 dialogue-api-v2.0 的測試腳本風格
"""
import requests
import json
import os
from typing import Optional

# --- Configuration ---
BASE_URL = "http://localhost:8000/api/dialogue"
AUDIO_FILE_PATH = "Recording.m4a"
DEFAULT_CHARACTER_ID = "patient_wang_001"

# 王大華的角色配置 (來自 config/characters.yaml)
PATIENT_CHARACTER_CONFIG = {
    "name": "王大華",
    "persona": "口腔癌病患",
    "backstory": "此為系統創建的預設角色，正在接受口腔癌治療。",
    "goal": "與醫護人員清楚溝通並了解治療計畫",
    "details": {
        "fixed_settings": {
            "流水編號": "1",
            "姓名": "王大華",
            "性別": "男",
            "目前診斷": "齒齦癌",
            "診斷分期": "pT2N0M0, stage II"
        },
        "floating_settings": {
            "年齡": "69",
            "目前接受治療場所": "病房",
            "目前治療階段": "手術後恢復期-普通病室",
            "目前治療狀態": "術後照護，傷口護理",
            "腫瘤復發": "無",
            "身高": "173",
            "體重": "76.8",
            "BMI": "25.7",
            "慢性病": "高血壓、糖尿病、慢性心衰竭",
            "用藥史": "脈優、得安穩、庫魯化錠",
            "目前用藥_文字": "阿莫西林 500 mg，一天三次（口服）",
            "身體功能分數(KPS)": "90"
        }
    }
}


def format_request_for_log(method: str, url: str, headers: Optional[dict] = None, 
                           data: Optional[dict] = None, files: Optional[dict] = None) -> str:
    """格式化請求資訊用於日誌"""
    log_lines = [
        f"Request Method: {method}",
        f"Request URL   : {url}",
    ]
    if data:
        log_lines.append(f"Form Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
    if files:
        file_details = {key: {"filename": val[0], "content_type": val[2] if len(val) > 2 else 'N/A'} 
                        for key, val in files.items()}
        log_lines.append(f"Files: {json.dumps(file_details, indent=2)}")
    return "\n".join(log_lines)


def print_response(test_name: str, response: requests.Response, request_log: str):
    """輸出回應結果"""
    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print('='*60)
    print("\n--- Request ---")
    print(request_log)
    print("\n--- Response ---")
    print(f"Status Code: {response.status_code}")
    
    try:
        response.raise_for_status()
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {response.text}")
    except json.JSONDecodeError:
        print(f"Raw Response: {response.text}")
    return None


def test_audio_input_m4a():
    """測試 /api/dialogue/audio_input 使用 M4A 音檔"""
    url = f"{BASE_URL}/audio_input"
    
    if not os.path.exists(AUDIO_FILE_PATH):
        print(f"❌ 找不到音檔: {AUDIO_FILE_PATH}")
        return None
    
    print(f"\n📁 使用音檔: {AUDIO_FILE_PATH}")
    print(f"   檔案大小: {os.path.getsize(AUDIO_FILE_PATH)} bytes")
    
    form_data = {
        'character_id': DEFAULT_CHARACTER_ID,
        'character_config_json': json.dumps(PATIENT_CHARACTER_CONFIG, ensure_ascii=False)
    }
    
    with open(AUDIO_FILE_PATH, 'rb') as f_audio:
        files_payload = {
            'audio_file': (os.path.basename(AUDIO_FILE_PATH), f_audio, 'audio/m4a')
        }
        request_log = format_request_for_log("POST", url, data=form_data, files=files_payload)
        response = requests.post(url, files=files_payload, data=form_data)
    
    result = print_response("Audio Input (M4A) - 醫護人員語音輸入", response, request_log)
    
    if result and result.get("status") == "success":
        print("\n✅ 測試成功!")
        print(f"   轉錄結果: {result.get('original_transcription')}")
        print(f"   Session ID: {result.get('session_id')}")
        print("\n   [AI 回應選項]:")
        for i, resp in enumerate(result.get('responses', []), 1):
            print(f"   {i}. {resp}")
        return result.get('session_id')
    else:
        print("\n❌ 測試失敗!")
        return None


def test_text_followup(session_id: str):
    """測試文字追問（多輪對話）"""
    url = f"{BASE_URL}/text"
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "text": "那您昨天睡得好嗎？有沒有其他不舒服的地方？",
        "character_id": DEFAULT_CHARACTER_ID,
        "character_config": PATIENT_CHARACTER_CONFIG,
        "session_id": session_id
    }
    
    request_log = f"Request URL: {url}\nPayload: {json.dumps(payload, indent=2, ensure_ascii=False)}"
    response = requests.post(url, data=json.dumps(payload, ensure_ascii=False), headers=headers)
    
    result = print_response("Text Follow-up - 醫護人員追問", response, request_log)
    
    if result and result.get("status") == "success":
        print("\n✅ 多輪對話測試成功!")
        print("\n   [AI 回應選項]:")
        for i, resp in enumerate(result.get('responses', []), 1):
            print(f"   {i}. {resp}")
    else:
        print("\n❌ 多輪對話測試失敗!")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Dialogue API M4A 測試")
    print("="*60)
    
    # Turn 1: 音訊輸入
    session_id = test_audio_input_m4a()
    
    # Turn 2: 文字追問 (如果 Turn 1 成功)
    if session_id:
        print("\n" + "-"*60)
        test_text_followup(session_id)
    
    print("\n" + "="*60)
    print("測試完成")
    print("="*60)
