import requests
import json
import time
import logging
import sys

# 設置日誌
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('config_debug.log')
    ]
)
logger = logging.getLogger("config_debug")

# API 端點
API_URL = "http://localhost:8000/api/dialogue/text"

def test_character_config():
    """專門測試 character_config 參數在 API 中的處理"""
    logger.info("=== 開始測試 character_config 參數處理 ===")
    
    # 基本角色配置
    basic_config = {
        "name": "Config Test Patient",
        "persona": "配置測試角色",
        "backstory": "這是一個特殊的配置測試角色",
        "goal": "測試 API 處理自定義配置的能力"
    }
    
    # 發送請求
    logger.info("發送請求")
    response = requests.post(
        API_URL,
        json={
            "text": "您好",
            "character_id": "config_test",
            "character_config": basic_config
        }
    )
    
    # 檢查回應狀態碼
    logger.info(f"回應狀態碼: {response.status_code}")
    
    try:
        # 解析回應 JSON
        response_json = response.json()
        logger.info(f"回應內容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
        
        # 檢查角色名稱
        if "responses" in response_json:
            for resp in response_json["responses"]:
                logger.info(f"檢查回應: {resp}")
                if "Patient_config_test" in resp:
                    logger.warning("使用了預設角色名稱 'Patient_config_test'，而不是客戶端提供的名稱 'Config Test Patient'")
                elif "Config Test Patient" in resp:
                    logger.info("使用了客戶端提供的角色名稱 'Config Test Patient'，配置正確")
                elif "抱歉" in resp and "無法正確回應" in resp:
                    logger.warning("回應處於 CONFUSED 狀態，可能是 LLM 連接問題")
                    
        # 檢查狀態
        if "state" in response_json:
            logger.info(f"對話狀態: {response_json['state']}")
            if response_json["state"] == "CONFUSED":
                logger.warning("對話處於 CONFUSED 狀態")
        
        # 獲取會話 ID
        if "session_id" in response_json:
            session_id = response_json["session_id"]
            logger.info(f"會話 ID: {session_id}")
            
            # 測試會話持久性和 character 記憶
            logger.info("測試會話持久性")
            time.sleep(2)
            
            # 發送第二個請求
            response2 = requests.post(
                API_URL,
                json={
                    "text": "請告訴我您的名字和年齡",
                    "character_id": "config_test",
                    "session_id": session_id
                }
            )
            
            # 檢查第二個回應
            logger.info(f"第二個請求狀態碼: {response2.status_code}")
            
            try:
                response2_json = response2.json()
                logger.info(f"第二個回應內容: {json.dumps(response2_json, ensure_ascii=False, indent=2)}")
                
                if "responses" in response2_json:
                    for resp in response2_json["responses"]:
                        if "Patient_config_test" in resp:
                            logger.warning("在持續會話中使用了預設角色名稱")
                        elif "Config Test Patient" in resp:
                            logger.info("在持續會話中使用了客戶端提供的角色名稱，配置正確")
                
                # 檢查會話 ID 匹配
                if "session_id" in response2_json:
                    if response2_json["session_id"] == session_id:
                        logger.info("會話 ID 匹配，會話持久性正常")
                    else:
                        logger.warning(f"會話 ID 不匹配: 原始={session_id}, 回應={response2_json['session_id']}")
                
            except json.JSONDecodeError:
                logger.error(f"無法解析第二個回應 JSON: {response2.text}")
        
    except json.JSONDecodeError:
        logger.error(f"無法解析 JSON 回應: {response.text}")
    
    logger.info("=== 測試完成 ===")

def test_detailed_config():
    """測試詳細的角色配置"""
    logger.info("=== 開始測試詳細角色配置 ===")
    
    # 詳細角色配置
    detailed_config = {
        "name": "Detailed Config Patient",
        "persona": "詳細配置測試角色",
        "backstory": "這是一個用於測試詳細配置的角色",
        "goal": "測試 API 處理詳細配置的能力",
        "details": {
            "fixed_settings": {
                "流水編號": 555,
                "年齡": 45,
                "性別": "女",
                "診斷": "配置測試診斷",
                "分期": "stage II",
                "腫瘤方向": "右側",
                "手術術式": "測試手術"
            },
            "floating_settings": {
                "目前接受治療場所": "測試病房",
                "關鍵字": "測試",
                "個案現況": "這是一個配置測試案例"
            }
        }
    }
    
    # 發送請求
    logger.info("發送請求")
    response = requests.post(
        API_URL,
        json={
            "text": "您好，請告訴我您的詳細情況",
            "character_id": "detail_test",
            "character_config": detailed_config
        }
    )
    
    # 檢查回應
    logger.info(f"回應狀態碼: {response.status_code}")
    
    try:
        # 解析回應 JSON
        response_json = response.json()
        logger.info(f"回應內容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
        
        # 檢查狀態
        if "state" in response_json:
            logger.info(f"對話狀態: {response_json['state']}")
        
        # 檢查回應中是否有提及 details 中的信息
        if "responses" in response_json:
            for resp in response_json["responses"]:
                logger.info(f"檢查回應: {resp}")
                
                # 檢查角色名稱
                if "Patient_detail_test" in resp:
                    logger.warning("使用了預設角色名稱，而不是客戶端提供的名稱")
                elif "Detailed Config Patient" in resp:
                    logger.info("使用了客戶端提供的角色名稱")
                    
                # 檢查詳細設置
                if any(detail in resp for detail in ["45歲", "女性", "配置測試診斷", "右側"]):
                    logger.info("回應中包含詳細配置中的信息")
                    
    except json.JSONDecodeError:
        logger.error(f"無法解析 JSON 回應: {response.text}")
    
    logger.info("=== 測試完成 ===")

if __name__ == "__main__":
    logger.info("開始診斷 character_config 參數處理問題")
    test_character_config()
    test_detailed_config()
    logger.info("診斷完成") 