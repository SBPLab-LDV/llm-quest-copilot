import requests
import json
import logging
import sys
import os

# 設置日誌記錄
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("audio_api_test_simple")

# API 端點
API_URL = "http://localhost:8000/api/dialogue/audio"

def test_audio_api_simplified():
    """簡化版音頻 API 測試 - 使用已有音頻文件"""
    logger.info("=== 測試音頻 API 對 character_config 參數的支持（簡化版）===")
    
    # 創建角色配置
    character_config = {
        "name": "Audio Test Simple",
        "persona": "簡化版音頻測試角色",
        "backstory": "這是一個用於簡化版測試的角色",
        "goal": "測試簡化版音頻 API 功能"
    }
    
    # 使用已有的音頻文件（如果不存在，會創建一個）
    test_audio_path = "test_audio.wav"
    if not os.path.exists(test_audio_path):
        # 生成一個簡單的正弦波音頻
        import numpy as np
        from scipy.io import wavfile
        
        sample_rate = 16000
        duration = 2  # 2秒鐘
        t = np.arange(0, duration, 1/sample_rate)
        audio = np.sin(2 * np.pi * 440 * t) * 32767 * 0.5  # 440Hz 正弦波
        audio = audio.astype(np.int16)
        
        wavfile.write(test_audio_path, sample_rate, audio)
        logger.info(f"創建了測試音頻文件: {test_audio_path}")
    
    try:
        # 準備請求數據
        with open(test_audio_path, "rb") as audio_file:
            files = {
                'audio_file': ('test_audio.wav', audio_file, 'audio/wav')
            }
            data = {
                'character_id': 'audio_simple_test',
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
                timeout=30
            )
            
            # 記錄回應
            logger.info(f"收到回應: {response.status_code}")
            logger.debug(f"回應頭: {dict(response.headers)}")
            
            if response.status_code == 200:
                # 如果回應是 JSON 格式
                try:
                    response_json = response.json()
                    logger.debug(f"回應內容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
                    logger.info("測試成功: 收到有效回應")
                    return response_json
                except json.JSONDecodeError:
                    logger.warning("回應不是有效的 JSON 格式")
                    logger.debug(f"原始回應: {response.text[:500]}")
            else:
                logger.error(f"請求失敗，狀態碼: {response.status_code}")
                logger.debug(f"錯誤信息: {response.text}")
    
    except Exception as e:
        logger.error(f"測試過程中發生錯誤: {e}")
    
    return None

if __name__ == "__main__":
    logger.info("開始簡化版音頻 API 測試")
    test_audio_api_simplified()
    logger.info("測試完成") 