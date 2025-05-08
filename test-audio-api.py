import requests
import json
import logging
import sys
import os
import tempfile
import numpy as np
from scipy.io import wavfile

# 設置日誌記錄
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 輸出到控制台
        logging.FileHandler('audio_api_test.log')  # 輸出到檔案
    ]
)
logger = logging.getLogger("audio_api_test")

# API 端點
API_URL = "http://localhost:8000/api/dialogue/audio"

def create_test_audio(text="這是一段測試音頻"):
    """創建測試用的音頻文件
    
    Args:
        text: 假定的音頻內容
        
    Returns:
        臨時音頻文件路徑
    """
    # 創建一個與文本長度相關的音頻
    sample_rate = 16000
    duration = min(2 + len(text) * 0.05, 10)  # 根據文本長度調整，最長10秒
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # 產生簡單的正弦波，頻率隨文本長度變化
    frequency = 440 + (len(text) % 10) * 30
    audio = np.sin(2 * np.pi * frequency * t) * 0.5
    
    # 轉換為16位整數
    audio_int16 = (audio * 32767).astype(np.int16)
    
    # 創建臨時文件
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_file_path = temp_file.name
    temp_file.close()
    
    # 保存為 WAV 文件
    wavfile.write(temp_file_path, sample_rate, audio_int16)
    logger.debug(f"已創建測試音頻文件: {temp_file_path}")
    
    return temp_file_path

def test_audio_api_with_character_config():
    """測試音頻 API 對 character_config 參數的支持"""
    logger.info("=== 測試音頻 API 對 character_config 參數的支持 ===")
    
    # 創建角色配置
    character_config = {
        "name": "Audio API Test Patient",
        "persona": "音頻 API 測試角色",
        "backstory": "這是一個專門用於測試音頻 API 的角色，能夠支持通過音頻方式交互。",
        "goal": "測試音頻 API 的角色配置功能是否正常",
        "details": {
            "fixed_settings": {
                "流水編號": 777,
                "年齡": 38,
                "性別": "女",
                "診斷": "音頻測試診斷",
                "分期": "stage I",
                "腫瘤方向": "左側",
                "手術術式": "音頻測試手術"
            },
            "floating_settings": {
                "目前接受治療場所": "音頻測試病房",
                "目前治療階段": "音頻測試階段",
                "腫瘤復發": "無",
                "關鍵字": "音頻",
                "個案現況": "這是一個音頻API測試案例，用於驗證系統能夠通過音頻處理角色配置。"
            }
        }
    }
    
    # 創建測試音頻文件
    audio_path = create_test_audio("您好，請告訴我您是誰")
    
    try:
        # 準備請求數據
        files = {
            'audio_file': ('test_audio.wav', open(audio_path, 'rb'), 'audio/wav')
        }
        data = {
            'character_id': 'audio_test_char',
            'response_format': 'text',
            'character_config_json': json.dumps(character_config, ensure_ascii=False)
        }
        
        # 記錄發送的請求
        logger.info(f"發送請求到 {API_URL}")
        logger.debug(f"請求數據: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        # 發送請求
        response = requests.post(
            API_URL,
            files=files,
            data=data,
            timeout=30  # 增加超時時間以便處理較長的請求
        )
        
        # 記錄回應狀態和頭信息
        logger.info(f"收到回應: {response.status_code}")
        logger.debug(f"回應頭: {dict(response.headers)}")
        
        # 如果回應是 JSON 格式，記錄回應體
        try:
            if response.text:
                response_json = response.json()
                logger.debug(f"回應內容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
                
                # 檢查回應是否包含指定角色名稱
                if any("Audio API Test Patient" in resp for resp in response_json.get("responses", [])):
                    logger.info("測試成功: 回應中包含客戶端提供的角色名稱")
                else:
                    logger.warning("測試警告: 回應中未包含客戶端提供的角色名稱")
                
                return response_json
            else:
                logger.warning("回應內容為空")
                return None
        except json.JSONDecodeError:
            logger.error(f"無法解析 JSON 回應: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"請求失敗: {e}")
        return None
    finally:
        # 刪除臨時音頻文件
        try:
            os.unlink(audio_path)
            logger.debug(f"已刪除臨時音頻文件: {audio_path}")
        except Exception as e:
            logger.error(f"刪除臨時文件時出錯: {e}")

def test_audio_api_with_session_continuity():
    """測試音頻 API 的會話連續性"""
    logger.info("=== 測試音頻 API 的會話連續性 ===")
    
    # 創建角色配置
    character_config = {
        "name": "Audio Continuity Test",
        "persona": "音頻會話連續性測試角色",
        "backstory": "這是一個用於測試音頻 API 會話連續性的角色。",
        "goal": "測試音頻 API 的會話連續性功能"
    }
    
    # 第一個請求：建立會話
    audio_path1 = create_test_audio("您好，請自我介紹")
    
    try:
        # 準備第一個請求數據
        files1 = {
            'audio_file': ('audio1.wav', open(audio_path1, 'rb'), 'audio/wav')
        }
        data1 = {
            'character_id': 'audio_continuity_test',
            'response_format': 'text',
            'character_config_json': json.dumps(character_config, ensure_ascii=False)
        }
        
        # 發送第一個請求
        logger.info("發送第一個請求建立會話")
        response1 = requests.post(API_URL, files=files1, data=data1)
        
        # 如果回應是 JSON 格式，獲取會話ID
        if response1.status_code == 200:
            response_json1 = response1.json()
            logger.debug(f"第一個回應內容: {json.dumps(response_json1, ensure_ascii=False, indent=2)}")
            
            # 獲取會話ID
            session_id = response_json1.get("session_id")
            if session_id:
                logger.info(f"獲得會話 ID: {session_id}")
                
                # 創建第二個測試音頻
                audio_path2 = create_test_audio("請告訴我您的診斷情況")
                
                # 準備第二個請求數據
                files2 = {
                    'audio_file': ('audio2.wav', open(audio_path2, 'rb'), 'audio/wav')
                }
                data2 = {
                    'character_id': 'audio_continuity_test',
                    'response_format': 'text',
                    'session_id': session_id
                }
                
                # 發送第二個請求
                logger.info("發送第二個請求測試會話連續性")
                response2 = requests.post(API_URL, files=files2, data=data2)
                
                # 檢查第二個回應
                if response2.status_code == 200:
                    response_json2 = response2.json()
                    logger.debug(f"第二個回應內容: {json.dumps(response_json2, ensure_ascii=False, indent=2)}")
                    
                    # 檢查會話ID是否一致
                    if response_json2.get("session_id") == session_id:
                        logger.info("測試成功：會話連續性正常")
                        return True
                    else:
                        logger.error("測試失敗：會話ID不匹配")
                else:
                    logger.error(f"第二個請求失敗: {response2.status_code}")
                
                # 清理第二個音頻文件
                try:
                    os.unlink(audio_path2)
                except Exception:
                    pass
            else:
                logger.error("測試失敗: 第一個回應中缺少會話ID")
        else:
            logger.error(f"第一個請求失敗: {response1.status_code}")
    
    except Exception as e:
        logger.error(f"測試過程中發生錯誤: {e}")
    finally:
        # 清理第一個音頻文件
        try:
            os.unlink(audio_path1)
        except Exception:
            pass
    
    return False

if __name__ == "__main__":
    logger.info("開始測試音頻 API")
    
    # 測試帶有角色配置的音頻 API
    test_audio_api_with_character_config()
    
    # 測試音頻 API 的會話連續性
    test_audio_api_with_session_continuity()
    
    logger.info("音頻 API 測試完成") 