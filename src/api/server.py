"""
對話系統 HTTP API 服務器

提供 HTTP 端點以便外部客戶端訪問對話系統功能。
"""
import os
import uuid
import tempfile
import logging
import json
from typing import Dict, Optional, List, Any
import asyncio
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import speech_recognition as sr
import uvicorn
import numpy as np
from scipy.io import wavfile
from fastapi.responses import FileResponse

# 設置日誌記錄
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 輸出到控制台
        logging.FileHandler('api_server.log')  # 輸出到文件
    ]
)
logger = logging.getLogger(__name__)

# 導入現有的對話系統
from ..core.dialogue import DialogueManager
from ..core.character import Character
from ..core.state import DialogueState

# 定義請求和回應模型
class TextRequest(BaseModel):
    """文本請求模型"""
    text: str
    character_id: str
    session_id: Optional[str] = None
    response_format: Optional[str] = "text"  # 可選值: "text" 或 "audio"
    character_config: Optional[Dict[str, Any]] = None  # 客戶端提供的角色配置

class DialogueResponse(BaseModel):
    """對話回應模型"""
    status: str
    responses: List[str]
    state: str
    dialogue_context: str
    session_id: str

# 會話存儲，用於維護多個客戶端的對話狀態
session_store: Dict[str, Dict[str, Any]] = {}

# 角色記憶體緩存，避免重複創建角色實例
character_cache: Dict[str, Character] = {}

# 創建 FastAPI 應用
app = FastAPI(
    title="對話系統 API",
    description="提供對話系統的 HTTP 接口，接收文本或音頻輸入並返回對話回應",
    version="1.0.0"
)

# 添加 CORS 中間件以支持跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加請求中間件來記錄請求體
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """記錄所有請求和請求體"""
    # 記錄請求信息
    logger.debug(f"接收到請求: {request.method} {request.url}")
    logger.debug(f"請求頭: {request.headers}")
    
    # 讀取並記錄請求體，但需要克隆它以便於後續讀取
    body = await request.body()
    logger.debug(f"原始請求體: {body}")
    
    # 重建請求以便於後續處理
    async def receive():
        return {"type": "http.request", "body": body}
    
    request._receive = receive
    
    # 處理請求並返回響應
    response = await call_next(request)
    return response

# 依賴注入：獲取或創建會話
async def get_or_create_session(
    request: Request,
    session_id: Optional[str] = None,
    character_id: Optional[str] = None,
    character_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """獲取現有會話或創建新會話

    Args:
        request: 原始請求對象，用於日誌記錄
        session_id: 客戶端提供的會話ID
        character_id: 角色ID，用於創建新會話時
        character_config: 客戶端提供的角色設定 (可選)

    Returns:
        會話數據字典
    """
    logger.debug(f"嘗試獲取或創建會話: session_id={session_id}, character_id={character_id}, character_config={'提供' if character_config else '未提供'}")
    
    # 如果已存在會話，則返回
    if session_id and session_id in session_store:
        logger.debug(f"找到現有會話: {session_id}")
        return session_store[session_id]
    
    # 嘗試從請求體獲取 character_id 和 character_config (如果未直接提供)
    if not character_id or character_config is None:
        try:
            # 重新讀取請求體
            body = await request.json()
            logger.debug(f"解析後的請求體: {body}")
            if "character_id" in body and not character_id:
                character_id = body["character_id"]
                logger.debug(f"從請求體提取 character_id: {character_id}")
            if "character_config" in body and character_config is None:
                character_config = body["character_config"]
                logger.debug(f"從請求體提取 character_config")
        except Exception as e:
            logger.error(f"從請求體提取數據時出錯: {e}")
        
    # 驗證 character_id
    if not character_id:
        logger.error("未提供 character_id")
        raise HTTPException(
            status_code=400, 
            detail="創建新會話需要提供 character_id"
        )
    
    # 獲取或創建角色實例
    if character_id not in character_cache:
        logger.debug(f"創建新角色: {character_id}")
        
        # 創建基本角色
        if character_config:
            # 嘗試使用客戶端提供的配置
            try:
                logger.info(f"使用客戶端提供的配置創建角色: {character_id}")
                logger.debug(f"配置內容: {json.dumps(character_config, ensure_ascii=False, indent=2)}")
                
                # 提取必要字段
                name = character_config.get("name", f"Patient_{character_id}")
                persona = character_config.get("persona", "一般病患")
                backstory = character_config.get("backstory", "無特殊病史記錄")
                goal = character_config.get("goal", "尋求醫療協助")
                details = character_config.get("details", None)
                
                character = Character(
                    name=name,
                    persona=persona,
                    backstory=backstory,
                    goal=goal,
                    details=details
                )
                logger.debug(f"成功使用客戶端配置創建角色: {character.name}")
            except Exception as e:
                logger.error(f"使用客戶端配置創建角色失敗: {e}", exc_info=True)
                # 使用預設值創建
                character = create_default_character(character_id)
        else:
            # 使用預設值創建
            character = create_default_character(character_id)
        
        character_cache[character_id] = character
    
    # 創建新會話ID
    new_session_id = session_id or str(uuid.uuid4())
    logger.debug(f"創建新會話: {new_session_id}")
    
    # 創建對話管理器
    try:
        dialogue_manager = create_dialogue_manager(
            character=character_cache[character_id],
            log_dir="logs/api"
        )
    except Exception as e:
        logger.error(f"創建對話管理器失敗: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"創建對話管理器失敗: {str(e)}"
        )
    
    # 存儲會話數據
    session_store[new_session_id] = {
        "dialogue_manager": dialogue_manager,
        "character_id": character_id,
        "created_at": asyncio.get_event_loop().time(),
        "last_activity": asyncio.get_event_loop().time(),
    }
    
    return session_store[new_session_id]

def create_default_character(character_id: str) -> Character:
    """創建預設角色實例
    
    Args:
        character_id: 角色ID
        
    Returns:
        Character 實例
    """
    logger.info(f"使用預設設置創建角色 {character_id}")
    
    # 創建基本預設角色
    return Character(
        name=f"Patient_{character_id}",
        persona="口腔癌病患",
        backstory="此為系統創建的預設角色，正在接受口腔癌治療。",
        goal="與醫護人員清楚溝通並了解治療計畫",
        details={
            "fixed_settings": {
                "流水編號": int(character_id) if character_id.isdigit() else 99,
                "年齡": 60,
                "性別": "男",
                "診斷": "口腔癌",
                "分期": "stage II",
                "腫瘤方向": "右側",
                "手術術式": "腫瘤切除+皮瓣重建"
            },
            "floating_settings": {
                "目前接受治療場所": "病房",
                "目前治療階段": "手術後/出院前",
                "目前治療狀態": "腫瘤切除術後，尚未進行化學治療與放射線置離療",
                "關鍵字": "恢復",
                "個案現況": "病人於一週前進行腫瘤切除手術，目前恢復狀況良好，但仍需觀察。"
            }
        }
    )

# 語音轉文本函數
async def speech_to_text(audio_file: UploadFile) -> str:
    """將上傳的音頻文件轉換為文本

    Args:
        audio_file: 上傳的音頻文件

    Returns:
        辨識出的文本
    """
    recognizer = sr.Recognizer()
    
    # 創建臨時文件
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        # 寫入上傳的音頻數據
        temp_file.write(await audio_file.read())
        temp_file.close()
        
        # 讀取音頻文件並轉換為文本
        with sr.AudioFile(temp_file.name) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="zh-TW")
            return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"音頻處理失敗: {str(e)}")
    finally:
        # 刪除臨時文件
        os.unlink(temp_file.name)

# 會話清理任務
async def cleanup_old_sessions(background_tasks: BackgroundTasks):
    """清理長時間未活動的會話

    Args:
        background_tasks: FastAPI 背景任務
    """
    current_time = asyncio.get_event_loop().time()
    session_timeout = 3600  # 1小時無活動則清理
    
    sessions_to_remove = []
    for session_id, session_data in session_store.items():
        if current_time - session_data["last_activity"] > session_timeout:
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        # 保存對話日誌後刪除會話
        session_store[session_id]["dialogue_manager"].save_interaction_log()
        del session_store[session_id]

# 添加一個輔助函數來處理回應格式化
async def format_dialogue_response(
    response_json: str,
    session_id: Optional[str] = None,
    session: Optional[Dict[str, Any]] = None
) -> DialogueResponse:
    """格式化對話回應
    
    Args:
        response_json: 對話管理器返回的 JSON 字符串
        session_id: 會話 ID
        session: 會話對象
    
    Returns:
        格式化的對話回應
    """
    # 解析回應
    logger.debug(f"格式化對話回應: {response_json}")
    
    try:
        response_dict = json.loads(response_json)
        logger.debug(f"解析後的 JSON 回應: {json.dumps(response_dict, ensure_ascii=False, indent=2)}")
    except json.JSONDecodeError as e:
        logger.error(f"解析 JSON 失敗: {e}")
        response_dict = {
            "responses": ["抱歉，處理您的請求時出現了問題"],
            "state": "CONFUSED",
            "dialogue_context": "未知上下文"
        }
    
    # 找出當前會話ID
    current_session_id = session_id
    if not current_session_id and session:
        for key, value in session_store.items():
            if value is session:
                current_session_id = key
                break
    
    # 確保所有必要的鍵都存在於字典中，使用合理的預設值
    if "responses" not in response_dict or not response_dict["responses"]:
        logger.warning("回應中缺少 responses 鍵或為空，使用默認值")
        response_dict["responses"] = ["抱歉，我需要一些時間處理您的問題"]
    
    if "state" not in response_dict:
        logger.warning("回應中缺少 state 鍵，使用默認值")
        response_dict["state"] = "CONFUSED"
    
    if "dialogue_context" not in response_dict:
        logger.warning("回應中缺少 dialogue_context 鍵，使用默認值")
        response_dict["dialogue_context"] = "未知上下文"
    
    # 處理 CONFUSED 狀態，提供更好的備用回應
    if response_dict["state"] == "CONFUSED" and session and "dialogue_manager" in session:
        character = session["dialogue_manager"].character
        logger.info(f"將 CONFUSED 回應替換為角色適當的回應")
        character_name = character.name
        character_persona = character.persona
        
        # 為避免每次返回相同的備用回應，我們可以提供幾種不同的選項
        fallback_responses = [
            f"您好，我是{character_name}。{character_persona}。您需要什麼幫助嗎？",
            f"抱歉，我理解您想了解更多關於我的情況。我是{character_name}，{character_persona}。",
            f"您好，我是{character_name}。我可能沒有完全理解您的問題，能請您換個方式說明嗎？",
            f"我是{character_name}，{character_persona}。抱歉，我現在可能沒法完全理解您的問題。"
        ]
        
        # 使用時間戳作為簡單的輪換機制
        import time
        index = int(time.time()) % len(fallback_responses)
        
        response_dict["responses"] = [fallback_responses[index]]
        response_dict["state"] = "NORMAL"  # 改為 NORMAL 狀態
        response_dict["dialogue_context"] = "一般問診對話"
        
        logger.info(f"生成備用回應: {response_dict['responses'][0]}")
    
    # 構建回應對象
    try:
        response = DialogueResponse(
            status="success",
            responses=response_dict["responses"],
            state=response_dict["state"],
            dialogue_context=response_dict["dialogue_context"],
            session_id=current_session_id or str(uuid.uuid4())
        )
        return response
    except Exception as e:
        logger.error(f"創建 DialogueResponse 時出錯: {e}", exc_info=True)
        # 提供一個回退方案，創建一個基本的回應
        return DialogueResponse(
            status="error",
            responses=["抱歉，處理您的請求時出現錯誤"],
            state="CONFUSED",
            dialogue_context="錯誤處理",
            session_id=current_session_id or str(uuid.uuid4())
        )

# API 路由
@app.post("/api/dialogue/text", response_model=DialogueResponse)
async def process_text_dialogue(
    request: Request,
    background_tasks: BackgroundTasks
):
    """處理文本對話請求

    Args:
        request: 原始請求對象
        background_tasks: FastAPI 背景任務

    Returns:
        對話回應
    """
    try:
        # 手動解析請求體
        logger.debug("開始處理文本對話請求")
        body = await request.json()
        logger.debug(f"解析後的請求體: {body}")
        
        # 創建請求模型
        text = body.get("text", "")
        character_id = body.get("character_id")
        session_id = body.get("session_id")
        response_format = body.get("response_format", "text")
        character_config = body.get("character_config")  # 提取客戶端提供的角色配置
        
        logger.debug(f"提取參數: text={text}, character_id={character_id}, session_id={session_id}, response_format={response_format}, character_config={'提供' if character_config else '未提供'}")
        
        # 參數檢查
        if not text:
            raise HTTPException(status_code=400, detail="必須提供 text 參數")
        if not character_id:
            raise HTTPException(status_code=400, detail="必須提供 character_id 參數")
        
        # 臨時解決方案：如果提供了 session_id 但不在 session_store 中，返回錯誤
        if session_id and session_id not in session_store:
            raise HTTPException(status_code=404, detail="找不到指定的會話，請創建新會話")
        
        # 如果有會話 ID，使用現有會話
        if session_id and session_id in session_store:
            session = session_store[session_id]
            # 更新會話活動時間
            session["last_activity"] = asyncio.get_event_loop().time()
        else:
            # 創建新會話 - 使用 get_or_create_session 處理 character_config
            try:
                session = await get_or_create_session(
                    request=request,
                    character_id=character_id,
                    character_config=character_config
                )
                session_id = next(key for key, value in session_store.items() if value is session)
            except Exception as e:
                logger.error(f"創建會話時出錯: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"創建會話失敗: {str(e)}"
                )
        
        # 在調用對話管理器前添加診斷信息
        logger.debug(f"使用的角色信息: id={character_id}, name={session['dialogue_manager'].character.name}")
        
        # 調用對話管理器處理用戶輸入
        dialogue_manager = session["dialogue_manager"]
        logger.debug(f"調用對話管理器處理: '{text}'")
        
        # 直接使用對話管理器處理
        response_json = await dialogue_manager.process_turn(text)
        
        # 排程清理舊會話
        background_tasks.add_task(cleanup_old_sessions, background_tasks)
        
        # 使用輔助函數格式化回應
        response = await format_dialogue_response(
            response_json=response_json,
            session_id=session_id,
            session=session
        )
        
        logger.debug(f"返回回應: {response}")
        
        # 如果需要語音回覆，轉換文本為語音
        if response_format == "audio":
            # 選擇第一個回覆選項作為語音內容
            text_to_speak = response.responses[0] if response.responses else "無回應"
            
            # 生成語音文件
            audio_file_path = dummy_tts(text_to_speak)
            
            # 創建背景任務以刪除臨時文件
            bg_tasks = BackgroundTasks()
            bg_tasks.add_task(os.unlink, audio_file_path)
            
            # 返回語音文件
            response = FileResponse(
                path=audio_file_path,
                media_type="audio/wav",
                filename=f"response_{hash(text_to_speak)}.wav",
                background=bg_tasks  # 使用正確創建的背景任務
            )
            # 添加會話ID到頭部
            if hasattr(response, "session_id"):
                response.headers["X-Session-ID"] = str(response.session_id)
            else:
                response.headers["X-Session-ID"] = str(session_id) if session_id else ""
            return response
        else:
            # 返回正常的文本回覆
            return response
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析錯誤: {e}")
        raise HTTPException(status_code=400, detail=f"無效的 JSON 格式: {str(e)}")
    except Exception as e:
        logger.error(f"處理文本對話請求時出錯: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"處理請求時發生錯誤: {str(e)}")

@app.post("/api/dialogue/audio", response_model=DialogueResponse)
async def process_audio_dialogue(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    character_id: str = Form(...),
    session_id: Optional[str] = Form(None),
    response_format: Optional[str] = Form("text"),  # 新增參數，默認為文本回覆
):
    """處理音頻對話請求

    Args:
        request: 原始請求對象
        background_tasks: FastAPI 背景任務
        audio_file: 上傳的音頻文件
        character_id: 角色ID
        session_id: 會話ID (可選)
        response_format: 回覆格式 (可選值: "text" 或 "audio")

    Returns:
        對話回應
    """
    # 註意: 由於 multipart/form-data 無法直接傳輸複雜的 JSON 數據，
    # 因此音頻 API 不支持直接接收 character_config 參數。
    # 建議使用文本 API 先創建帶有角色配置的會話，然後將會話 ID 傳遞給音頻 API。
    
    # 檢查會話是否存在
    if not session_id or session_id not in session_store:
        logger.warning(f"音頻 API 請求未提供有效的會話 ID: {session_id}")
        raise HTTPException(
            status_code=400,
            detail="音頻 API 需要提供有效會話 ID。請先使用文本 API 創建會話，並提供角色配置。"
        )
    
    # 獲取會話
    session = session_store[session_id]
    
    # 語音轉文本
    text = await speech_to_text(audio_file)
    
    # 更新會話活動時間
    session["last_activity"] = asyncio.get_event_loop().time()
    
    # 調用對話管理器處理用戶輸入
    dialogue_manager = session["dialogue_manager"]
    logger.debug(f"調用對話管理器處理音頻轉換文本: '{text}'")
    response_json = await dialogue_manager.process_turn(text)
    
    # 排程清理舊會話
    background_tasks.add_task(cleanup_old_sessions, background_tasks)
    
    # 使用輔助函數格式化回應
    response = await format_dialogue_response(
        response_json=response_json,
        session_id=session_id,
        session=session
    )
    
    logger.debug(f"返回音頻對話回應: {response}")
    
    # 如果需要語音回覆，轉換文本為語音
    if response_format == "audio":
        # 選擇第一個回覆選項作為語音內容
        text_to_speak = response.responses[0] if response.responses else "無回應"
        
        # 生成語音文件
        audio_file_path = dummy_tts(text_to_speak)
        
        # 創建背景任務以刪除臨時文件
        bg_tasks = BackgroundTasks()
        bg_tasks.add_task(os.unlink, audio_file_path)
        
        # 返回語音文件
        response = FileResponse(
            path=audio_file_path,
            media_type="audio/wav",
            filename=f"response_{hash(text_to_speak)}.wav",
            background=bg_tasks  # 使用正確創建的背景任務
        )
        # 添加會話ID到頭部
        response.headers["X-Session-ID"] = str(session_id) if session_id else ""
        return response
    else:
        # 返回正常的文本回覆
        return response

@app.get("/api/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "ok", "active_sessions": len(session_store)}

# 添加一個簡單的 dummy TTS 函數
def dummy_tts(text, voice_id="default"):
    """生成一個 dummy 語音文件
    
    Args:
        text: 要轉換為語音的文本
        voice_id: 語音 ID (目前未使用)
        
    Returns:
        臨時文件路徑
    """
    logger.debug(f"生成 dummy 語音: '{text}'")
    # 創建一個與文本長度相關的音頻（只是為了讓不同文本有不同音頻）
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
    logger.debug(f"已生成語音文件: {temp_file_path}")
    
    return temp_file_path

# 添加一個新函數創建對話管理器，並添加詳細日誌記錄
def create_dialogue_manager(character: Character, log_dir: str = "logs/api") -> DialogueManager:
    """創建對話管理器並添加詳細日誌記錄
    
    Args:
        character: 角色對象
        log_dir: 日誌目錄
    
    Returns:
        DialogueManager 實例
    """
    logger.debug(f"創建對話管理器，角色: {character.name}, 類型: {type(character)}")
    
    # 使用與獨立測試腳本相同的方式創建 DialogueManager
    try:
        # 僅使用必要參數
        manager = DialogueManager(character)
        logger.debug(f"成功創建對話管理器: {type(manager)}")
        return manager
    except Exception as e:
        logger.error(f"創建對話管理器失敗: {e}", exc_info=True)
        raise

# 如果直接運行此模塊，啟動服務器
if __name__ == "__main__":
    # 啟動前清理角色和會話緩存
    character_cache.clear()
    session_store.clear()
    logger.info("已清理角色和會話緩存，啟動服務器...")
    
    # 啟動服務器
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True) 