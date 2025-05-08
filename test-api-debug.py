import requests
import json
import time
import sys
import logging

# 設置超詳細的日誌記錄
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 輸出到控制台
        logging.FileHandler('api_debug.log')  # 輸出到檔案
    ]
)
logger = logging.getLogger("api_debug")

# API 端點
API_URL = "http://localhost:8000/api/dialogue/text"

def debug_post_request(*, url, data, description):
    """發送 POST 請求並詳細記錄每一步
    
    Args:
        url: API 端點 URL
        data: 請求數據 (JSON)
        description: 請求描述 (用於日誌)
        
    Returns:
        API 回應 (JSON) 或 None (如果失敗)
    """
    logger.info(f"=== 開始 {description} ===")
    
    # 記錄請求詳情
    logger.debug(f"請求 URL: {url}")
    logger.debug(f"請求數據: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    try:
        logger.debug("發送請求...")
        start_time = time.time()
        response = requests.post(url, json=data, timeout=30)
        end_time = time.time()
        
        # 記錄回應時間
        logger.debug(f"收到回應，耗時: {end_time - start_time:.2f} 秒")
        logger.debug(f"回應狀態碼: {response.status_code}")
        logger.debug(f"回應頭: {dict(response.headers)}")
        
        # 記錄並解析回應內容
        if response.text:
            logger.debug(f"原始回應內容: {response.text}")
            try:
                response_json = response.json()
                logger.debug(f"解析後的 JSON 回應: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
                
                # 分析回應內容
                if "status" in response_json:
                    logger.info(f"回應狀態: {response_json['status']}")
                if "state" in response_json:
                    logger.info(f"對話狀態: {response_json['state']}")
                if "dialogue_context" in response_json:
                    logger.info(f"對話上下文: {response_json['dialogue_context']}")
                if "session_id" in response_json:
                    logger.info(f"會話 ID: {response_json['session_id']}")
                if "responses" in response_json:
                    for i, resp in enumerate(response_json["responses"]):
                        logger.info(f"回應選項 {i+1}: {resp}")
                
                logger.info(f"=== 完成 {description} ===")
                return response_json
            except json.JSONDecodeError as e:
                logger.error(f"無法解析 JSON 回應: {e}")
                logger.info(f"=== 失敗 {description} ===")
                return None
        else:
            logger.warning("回應內容為空")
            logger.info(f"=== 失敗 {description} ===")
            return None
    
    except requests.exceptions.RequestException as e:
        logger.error(f"請求異常: {e}")
        logger.info(f"=== 失敗 {description} ===")
        return None

def debug_character_config_issue():
    """診斷 character_config 參數的問題"""
    logger.info("開始診斷 character_config 參數的問題")
    
    # 測試 1: 使用完整的 character_config
    logger.info("測試 1: 使用完整的 character_config")
    
    # 創建詳細的角色配置
    character_config = {
        "name": "Debug Test Patient",
        "persona": "除錯測試角色",
        "backstory": "這是一個專用於診斷 API 問題的角色，具有完整的設定。",
        "goal": "診斷 API 的 character_config 參數處理問題",
        "details": {
            "fixed_settings": {
                "流水編號": 123,
                "年齡": 35,
                "性別": "女",
                "診斷": "除錯診斷",
                "分期": "stage II",
                "腫瘤方向": "左側",
                "手術術式": "診斷性手術"
            },
            "floating_settings": {
                "目前接受治療場所": "除錯測試病房",
                "目前治療階段": "診斷期",
                "腫瘤復發": "無",
                "關鍵字": "除錯",
                "個案現況": "這是一個診斷問題用的測試案例"
            }
        }
    }
    
    # 發送請求 1: 創建帶有詳細配置的角色
    response1 = debug_post_request(
        url=API_URL,
        data={
            "text": "您好，請告訴我您是誰？",
            "character_id": "debug_test",
            "response_format": "text",
            "character_config": character_config
        },
        description="初始請求 - 帶有完整角色配置"
    )
    
    if not response1 or "session_id" not in response1:
        logger.error("測試 1 失敗: 無法創建會話")
        return
    
    session_id = response1["session_id"]
    
    # 測試 2: 使用剛創建的會話 ID 發送第二個請求
    logger.info("測試 2: 使用會話 ID 發送後續請求")
    
    # 等待 2 秒，確保服務器有足夠時間處理
    time.sleep(2)
    
    # 發送請求 2: 使用相同的會話 ID
    response2 = debug_post_request(
        url=API_URL,
        data={
            "text": "請告訴我您的診斷和治療情況",
            "character_id": "debug_test",
            "session_id": session_id,
            "response_format": "text"
        },
        description="後續請求 - 使用會話 ID"
    )
    
    if not response2:
        logger.error("測試 2 失敗: 無法接收回應")
        return
    
    # 測試 3: 使用最小化的角色配置
    logger.info("測試 3: 使用最小化的角色配置")
    
    # 創建最小化角色配置
    minimal_config = {
        "name": "Minimal Debug Patient",
        "persona": "最小化除錯角色",
        "backstory": "這是一個最小化的角色配置，用於診斷問題",
        "goal": "測試最小化角色配置"
    }
    
    # 發送請求 3: 創建帶有最小化配置的角色
    response3 = debug_post_request(
        url=API_URL,
        data={
            "text": "您好，請告訴我您是誰？",
            "character_id": "minimal_debug",
            "response_format": "text",
            "character_config": minimal_config
        },
        description="測試最小化角色配置"
    )
    
    if not response3 or "session_id" not in response3:
        logger.error("測試 3 失敗: 無法使用最小化配置創建會話")
        return
    
    # 測試 4: 使用系統默認角色（不提供 character_config）
    logger.info("測試 4: 使用系統默認角色（不提供 character_config）")
    
    # 發送請求 4: 僅提供 character_id
    response4 = debug_post_request(
        url=API_URL,
        data={
            "text": "您好，請告訴我您是誰？",
            "character_id": "default_debug",
            "response_format": "text"
        },
        description="測試系統默認角色"
    )
    
    if not response4 or "session_id" not in response4:
        logger.error("測試 4 失敗: 無法使用系統默認角色創建會話")
        return
    
    # 診斷結果總結
    logger.info("=== 診斷結果摘要 ===")
    logger.info(f"測試 1 (完整配置): {'通過' if response1 and 'session_id' in response1 else '失敗'}")
    logger.info(f"測試 2 (會話連續性): {'通過' if response2 and response2.get('session_id') == session_id else '失敗'}")
    logger.info(f"測試 3 (最小化配置): {'通過' if response3 and 'session_id' in response3 else '失敗'}")
    logger.info(f"測試 4 (系統默認角色): {'通過' if response4 and 'session_id' in response4 else '失敗'}")
    
    # 分析問題
    logger.info("=== 問題分析 ===")
    
    # 檢查回應中的 CONFUSED 狀態
    has_confused_state = any(
        response and response.get("state") == "CONFUSED"
        for response in [response1, response2, response3, response4]
    )
    
    if has_confused_state:
        logger.info("問題: 部分或全部回應處於 CONFUSED 狀態，這表明 LLM 未能正確生成回應")
        logger.info("可能原因:")
        logger.info("1. 與 Gemini API 的連接問題")
        logger.info("2. API 密鑰設置不正確或已過期")
        logger.info("3. 提示詞生成有問題")
        logger.info("4. character_config 參數沒有被正確傳遞給 LLM")
    
    # 檢查角色名稱
    for i, response in enumerate([response1, response2, response3, response4], 1):
        if response and "responses" in response:
            for r in response["responses"]:
                if "病患角色" in r and any(name in r for name in ["Patient_", "我是Patient"]):
                    logger.info(f"問題: 測試 {i} 的回應顯示使用了預設角色名稱，而非客戶端提供的名稱")
                    logger.info("可能原因: get_or_create_session 函數未正確使用 character_config 參數")
                    break

if __name__ == "__main__":
    logger.info("開始診斷 API 的 character_config 參數處理問題")
    debug_character_config_issue()
    logger.info("診斷完成") 