import requests
import json
import time
import logging
import sys

# 設置詳細的日誌記錄
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 輸出到控制台
        logging.FileHandler('api_test.log')  # 輸出到檔案
    ]
)
logger = logging.getLogger("api_test")

# API 端點
API_URL = "http://localhost:8000/api/dialogue/text"

def send_request(text, character_id, character_config=None, session_id=None):
    """發送 POST 請求到對話 API
    
    Args:
        text: 用戶輸入文本
        character_id: 角色 ID
        character_config: 角色配置（可選）
        session_id: 會話 ID（可選）
        
    Returns:
        API 回應
    """
    # 準備請求數據
    request_data = {
        "text": text,
        "character_id": character_id,
        "response_format": "text"
    }
    
    if session_id:
        request_data["session_id"] = session_id
        
    if character_config:
        request_data["character_config"] = character_config
    
    # 記錄發送的請求
    logger.info(f"發送請求到 {API_URL}")
    logger.debug(f"請求數據: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    
    # 發送請求
    try:
        response = requests.post(
            API_URL,
            json=request_data,
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

def test_full_character_config():
    """測試完整的角色配置"""
    logger.info("=== 測試完整的角色配置 ===")
    
    # 創建詳細的角色配置
    character_config = {
        "name": "API Test Patient",
        "persona": "API測試角色",
        "backstory": "這是一個專門用於測試 API 的角色，具有完整的設定。",
        "goal": "測試 API 的角色配置功能是否正常",
        "details": {
            "fixed_settings": {
                "流水編號": 888,
                "年齡": 42,
                "性別": "男",
                "診斷": "API測試診斷",
                "分期": "stage II",
                "腫瘤方向": "右側",
                "手術術式": "API測試手術"
            },
            "floating_settings": {
                "目前接受治療場所": "API測試病房",
                "目前治療階段": "手術後恢復期",
                "腫瘤復發": "無",
                "關鍵字": "API測試",
                "個案現況": "這是一個API測試案例，用於驗證系統能否正確處理角色配置。"
            }
        }
    }
    
    # 發送第一個請求
    logger.info("步驟 1: 發送初始請求建立會話")
    response = send_request(
        text="您好，請告訴我您的診斷和目前狀況",
        character_id="api_test_full", 
        character_config=character_config
    )
    
    if not response:
        logger.error("測試失敗: 未收到回應")
        return False
    
    # 檢查回應是否包含必要的字段
    if "session_id" not in response:
        logger.error("測試失敗: 回應中缺少 session_id")
        return False
    
    # 保存會話 ID 用於後續請求
    session_id = response["session_id"]
    logger.info(f"獲得會話 ID: {session_id}")
    
    # 檢查角色是否已正確創建
    logger.info("步驟 2: 發送後續請求測試會話連續性")
    time.sleep(1)  # 稍等一秒，避免請求太快
    
    # 發送第二個請求
    response2 = send_request(
        text="您在接受什麼樣的治療？",
        character_id="api_test_full",
        session_id=session_id
    )
    
    if not response2:
        logger.error("測試失敗: 第二次請求未收到回應")
        return False
    
    # 檢查會話連續性
    if response2.get("session_id") != session_id:
        logger.error(f"測試失敗: 會話 ID 不匹配 (原始: {session_id}, 回應: {response2.get('session_id')})")
        return False
    
    logger.info("測試成功: 完整角色配置功能正常")
    return True

def test_minimal_character_config():
    """測試最小化的角色配置"""
    logger.info("=== 測試最小化的角色配置 ===")
    
    # 創建最小必要的角色配置
    character_config = {
        "name": "Minimal Patient",
        "persona": "最小化API測試角色",
        "backstory": "這是一個用於測試最小化角色配置的角色",
        "goal": "測試最小化角色配置是否能被正確處理"
    }
    
    # 發送請求
    logger.info("發送帶有最小化角色配置的請求")
    response = send_request(
        text="您好，請自我介紹一下",
        character_id="api_test_minimal",
        character_config=character_config
    )
    
    if not response:
        logger.error("測試失敗: 未收到回應")
        return False
    
    # 檢查回應是否包含必要的字段
    if "session_id" not in response:
        logger.error("測試失敗: 回應中缺少 session_id")
        return False
    
    logger.info("測試成功: 最小化角色配置功能正常")
    return True

def test_default_character():
    """測試使用系統默認角色"""
    logger.info("=== 測試系統默認角色 ===")
    
    # 不提供角色配置，只提供 character_id
    logger.info("發送不帶角色配置的請求")
    response = send_request(
        text="您好，請告訴我您是誰",
        character_id="api_test_default"
    )
    
    if not response:
        logger.error("測試失敗: 未收到回應")
        return False
    
    # 檢查回應是否包含必要的字段
    if "session_id" not in response:
        logger.error("測試失敗: 回應中缺少 session_id")
        return False
    
    logger.info("測試成功: 默認角色功能正常")
    return True

if __name__ == "__main__":
    logger.info("開始 API 測試")
    
    # 運行完整角色配置測試
    full_result = test_full_character_config()
    
    # 運行最小化角色配置測試
    minimal_result = test_minimal_character_config()
    
    # 運行默認角色測試
    default_result = test_default_character()
    
    # 輸出總結
    logger.info("=== 測試結果摘要 ===")
    logger.info(f"完整角色配置測試: {'通過' if full_result else '失敗'}")
    logger.info(f"最小化角色配置測試: {'通過' if minimal_result else '失敗'}")
    logger.info(f"默認角色測試: {'通過' if default_result else '失敗'}") 