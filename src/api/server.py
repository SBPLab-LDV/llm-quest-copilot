#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""對話系統 API 服務器。
提供了基於 FastAPI 的接口，可以與對話系統進行交互。
"""

import os
import uuid
import time
import asyncio
import logging
import tempfile
import json
from datetime import datetime
from typing import Dict, Optional, List, Any, Union
import sys
import codecs
from dataclasses import asdict
import yaml

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Request, Body
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加更完整的錯誤處理和日誌記錄
import traceback

# 自定義 StreamHandler 來處理 Windows 控制台編碼問題
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # 安全輸出，捕獲任何編碼錯誤
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                # 對於 Windows 控制台，移除不能顯示的字符或使用替代字符
                safe_msg = "".join(c if ord(c) < 128 else '?' for c in msg)
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# 設置日誌記錄器，確保使用 UTF-8 編碼
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_server.log', mode='w', encoding='utf-8')
    ]
)

# 添加安全控制台處理器
console_handler = SafeStreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# 獲取根日誌記錄器並添加處理器
root_logger = logging.getLogger()
root_logger.addHandler(console_handler)

# 模組日誌記錄器
logger = logging.getLogger(__name__)

# 導入現有的對話系統
from ..core.dialogue_factory import create_dialogue_manager
from ..core.character import Character
from ..core.state import DialogueState
from ..utils.config import load_character
from ..utils.speech_input import SpeechInput
from ..utils.config import load_config
from ..core.dspy.config import DSPyConfig
from ..core.audio.context_utils import (
    format_history_for_audio,
    build_available_audio_contexts,
    summarize_character,
    build_audio_template_rules,
)
from ..core.dspy.audio_modules import (
    get_audio_prompt_composer,
    get_audio_disfluency_module,
)
from ..llm.dspy_gemini_adapter import start_dspy_debug_log
from .performance_monitor import get_performance_monitor
from .health_monitor import get_health_monitor

# SpeechInput Handler Initialization
speech_input_handler: Optional[SpeechInput] = None
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.yaml')

try:
    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    google_api_key_path = config_data.get("google_api_key")

    if google_api_key_path:
        speech_input_handler = SpeechInput(google_api_key=google_api_key_path, debug_mode=config_data.get('debug_mode', False))
        logger.info(f"SpeechInput handler initialized successfully using key from {CONFIG_FILE_PATH}.")
    else:
        logger.warning(f"'google_api_key' not found or empty in {CONFIG_FILE_PATH}. Speech input via speech_recognition will be unavailable.")

except FileNotFoundError:
    logger.warning(f"Configuration file {CONFIG_FILE_PATH} not found. Speech input via speech_recognition will be unavailable.")
except yaml.YAMLError as e:
    logger.error(f"Error parsing YAML configuration file {CONFIG_FILE_PATH}: {e}", exc_info=True)
    logger.warning("Speech input via speech_recognition will be unavailable due to YAML parsing error.")
except Exception as e:
    logger.error(f"Failed to initialize SpeechInput handler from config: {e}", exc_info=True)
    logger.warning("Speech input via speech_recognition will be unavailable due to an unexpected error during initialization.")

# 定義請求和回應模型
class TextRequest(BaseModel):
    """文本請求模型"""
    text: str
    character_id: str
    session_id: Optional[str] = None
    character_config: Optional[Dict[str, Any]] = None  # 客戶端提供的角色配置

class DialogueResponse(BaseModel):
    """對話回應模型"""
    status: str
    responses: List[str]
    state: str
    dialogue_context: str
    session_id: str
    inferred_speaker_role: Optional[str] = None  # [已棄用] 保留欄位，總是回傳 None
    speech_recognition_options: Optional[List[str]] = None  # 新增: 語音識別可能的選項
    original_transcription: Optional[str] = None  # 新增: 原始語音轉錄文本
    raw_transcript: Optional[str] = None  # Self-annotation: 原始轉錄片段
    keyword_completion: Optional[List[Dict[str, Any]]] = None  # Self-annotation: 關鍵詞補全
    implementation_version: Optional[str] = None  # Phase 5: 實現版本標記
    performance_metrics: Optional[Dict[str, Any]] = None  # Phase 5: 性能指標
    processing_info: Optional[Dict[str, Any]] = None  # Unified/consistency摘要（可選）
    logs: Optional[Dict[str, Any]] = None  # 當前會話的日誌路徑（chat_gui / dspy_debug）

class SelectResponseRequest(BaseModel):
    """選擇回應請求模型"""
    session_id: str
    selected_response: str

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

# 開發用：查詢指定 session 的對話歷史（受可選令牌保護）
@app.get("/api/dev/session/{session_id}/history")
async def get_session_history(session_id: str, token: Optional[str] = None):
    """取得指定 session 的對話歷史。

    安全性：若環境變數 DEBUG_API_TOKEN 已設定，則必須提供相同的 token 作為查詢參數；
    若未設定，則不檢查 token（開發環境使用）。
    """
    env_token = os.getenv("DEBUG_API_TOKEN")
    if env_token and token != env_token:
        raise HTTPException(status_code=403, detail="Forbidden: invalid token")

    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session = session_store[session_id]
    dm = session.get("dialogue_manager")
    if dm is None:
        raise HTTPException(status_code=500, detail="Dialogue manager missing in session")

    history = list(getattr(dm, "conversation_history", []))
    impl = session.get("implementation_version", "unknown")
    log_path = getattr(dm, "log_filepath", None)

    return {
        "status": "success",
        "session_id": session_id,
        "implementation_version": impl,
        "conversation_history": history,
        "log_file": log_path,
    }

# 開發用：動態調整 LM 歷史視窗大小（影響 Unified 模組的提示歷史）
@app.post("/api/dev/config/set_max_history")
async def set_max_history(request: dict = Body(...)):
    """設定環境變數 DSPY_MAX_HISTORY 以控制歷史視窗（1–20）。"""
    try:
        trace_id = ""
        value = int(request.get("max_history", 3))
        if not (1 <= value <= 20):
            raise HTTPException(status_code=400, detail="max_history must be between 1 and 20")
        os.environ["DSPY_MAX_HISTORY"] = str(value)
        logger.info(f"Set DSPY_MAX_HISTORY to {value}")
        return {"status": "success", "DSPY_MAX_HISTORY": value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set max history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
            # 檢測請求類型
            content_type = request.headers.get("content-type", "")
            
            if "application/json" in content_type:
                # 如果是 JSON 請求
                body = await request.json()
                logger.debug(f"解析後的 JSON 請求體: {body}")
                if "character_id" in body and not character_id:
                    character_id = body["character_id"]
                    logger.debug(f"從 JSON 請求體提取 character_id: {character_id}")
                if "character_config" in body and character_config is None:
                    character_config = body["character_config"]
                    logger.debug(f"從 JSON 請求體提取 character_config")
            elif "multipart/form-data" in content_type:
                # 如果是多部分表單請求（如音頻上傳），則 character_config 可能來自 character_config_json 欄位
                form = await request.form()
                logger.debug(f"解析後的多部分表單數據: {form}")
                
                if "character_id" in form and not character_id:
                    character_id = form["character_id"]
                    logger.debug(f"從表單提取 character_id: {character_id}")
                
                if "character_config_json" in form and character_config is None:
                    try:
                        character_config_json = form["character_config_json"]
                        character_config = json.loads(character_config_json)
                        logger.debug(f"從表單 character_config_json 字段提取並解析 character_config")
                    except json.JSONDecodeError as e:
                        logger.error(f"解析表單中的 character_config_json 失敗: {e}")
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
                
                # 檢查 character_config 是否為字符串，若是則嘗試解析為字典
                if isinstance(character_config, str):
                    try:
                        logger.info("character_config 是字符串，嘗試解析為 JSON")
                        character_config = json.loads(character_config)
                        logger.info("成功將 character_config 字符串解析為字典")
                    except json.JSONDecodeError as e:
                        logger.error(f"解析 character_config 字符串失敗: {e}")
                        # 解析失敗則改為從 characters.yaml 載入，失敗再回退預設
                        try:
                            character = load_character(character_id)
                            logger.info(f"已從配置載入角色: {character.name}")
                        except Exception as le:
                            logger.warning(f"從配置載入角色失敗，使用預設: {le}")
                            character = create_default_character(character_id)
                
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
                # 嘗試從配置載入，失敗再回退預設
                try:
                    character = load_character(character_id)
                    logger.info(f"已從配置載入角色: {character.name}")
                except Exception as le:
                    logger.warning(f"從配置載入角色失敗，使用預設: {le}")
                    character = create_default_character(character_id)
        else:
            # 未提供客戶端配置 -> 先嘗試從 characters.yaml 載入
            try:
                character = load_character(character_id)
                logger.info(f"已從配置載入角色: {character.name}")
            except Exception as le:
                logger.warning(f"從配置載入角色失敗，使用預設: {le}")
                character = create_default_character(character_id)
        
        character_cache[character_id] = character
    
    # 創建新會話ID
    new_session_id = session_id or str(uuid.uuid4())
    logger.debug(f"創建新會話: {new_session_id}")
    
    # 創建對話管理器
    try:
        dialogue_manager, implementation_version, debug_log_path = create_dialogue_manager_with_monitoring(
            character=character_cache[character_id],
            log_dir="logs/api",
            session_id=new_session_id,
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
        "implementation_version": implementation_version,  # Phase 5: 記錄實現版本
        "created_at": asyncio.get_event_loop().time(),
        "last_activity": asyncio.get_event_loop().time(),
        "logs": {
            "chat_gui": getattr(dialogue_manager, 'log_filepath', None),
            "dspy_debug": str(debug_log_path) if debug_log_path else None,
        },
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
async def speech_to_text(
    audio_file: UploadFile,
    *,
    dialogue_manager: Optional[Any] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """將上傳的音頻文件轉換為文本，並提供多個可能的完整句子選項

    Args:
        audio_file: 上傳的音頻文件（支持 WAV, M4A, MP3, AAC 等格式）

    Returns:
        包含原始識別和多個選項的字典
    """
    logger.debug(f"開始處理音頻文件: {audio_file.filename}")
    
    temp_files = []  # 追蹤需要刪除的臨時文件
    trace_id = ""
    
    try:
        # 從文件名獲取擴展名
        import mimetypes
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        if not file_ext:
            file_ext = '.wav'  # 默認擴展名
        
        # 保存上傳的文件，使用原始擴展名
        original_audio_path = f"temp_audio_{uuid.uuid4()}{file_ext}"
        temp_files.append(original_audio_path)
        
        with open(original_audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        logger.debug(f"已保存臨時文件: {original_audio_path}")
        
        # 導入音頻處理工具
        from ..utils.audio_processor import check_audio_format, preprocess_audio, get_audio_mime_type
        
        # 檢查音頻格式
        if not check_audio_format(original_audio_path):
            logger.warning(f"上傳的音頻格式無效或不支持: {original_audio_path}")
            return {
                "original": "音頻格式無效",
                "options": ["您好，上傳的音頻格式不支持。支持的格式包括：WAV, M4A, MP3, AAC, OGG, FLAC。"]
            }
        
        # 獲取 MIME 類型
        mime_type = get_audio_mime_type(original_audio_path)
        logger.debug(f"音頻 MIME 類型: {mime_type}")
        
        # 對於 WAV 格式，進行預處理以優化識別
        # 對於其他格式，直接使用原始文件
        if file_ext == '.wav':
            processed_audio_path = f"processed_audio_{uuid.uuid4()}.wav"
            temp_files.append(processed_audio_path)
            
            processed_audio_path = preprocess_audio(
                input_file=original_audio_path,
                output_file=processed_audio_path
            )
            logger.debug(f"WAV 音頻預處理完成: {processed_audio_path}")
        else:
            # 其他格式直接使用
            logger.debug(f"使用原始音頻文件: {original_audio_path}")
            processed_audio_path = original_audio_path
        
        # 使用 GeminiClient 進行語音識別
        try:
            from ..llm.gemini_client import GeminiClient
            import json

            cfg = load_config()
            audio_cfg = cfg.get('audio', {}) if isinstance(cfg, dict) else {}
            use_ctx = bool(audio_cfg.get('use_context', False))
            # 依請求上下文決定是否注入角色與歷史
            character_obj = getattr(dialogue_manager, 'character', None) if (use_ctx and dialogue_manager) else None
            history_list = getattr(dialogue_manager, 'conversation_history', None) if (use_ctx and dialogue_manager) else None

            gemini_client = GeminiClient()
            logger.info(f"使用 Gemini 進行音頻識別: {processed_audio_path}")

            import uuid as _uuid
            trace_id = str(_uuid.uuid4())

            try:
                transcription_json = gemini_client.transcribe_audio(
                    processed_audio_path,
                    character=character_obj if use_ctx else None,
                    conversation_history=history_list if use_ctx else None,
                    session_id=session_id,
                    trace_id=trace_id,
                )
            except Exception:
                transcription_json = gemini_client.transcribe_audio(processed_audio_path)

            try:
                result = json.loads(transcription_json)

                # 提取 self-annotation 欄位
                raw_transcript = result.get("raw_transcript", "")
                keyword_completion = result.get("keyword_completion", [])
                original = result.get("original", "")
                options = result.get("options", [])

                logger.info(f"音頻識別成功: raw_transcript='{raw_transcript}', 原始='{original}', 選項數={len(options)}")

                if not original or original.startswith("無法識別") or original.startswith("音頻識別過程中發生錯誤"):
                    logger.warning(f"音頻識別失敗或沒有識別出有效內容: {original}")
                    return {
                        "original": original,
                        "options": ["您好，我沒能清楚聽到您的問題。請問您能再說一次嗎？"]
                    }

                if not options or len(options) < 1:
                    options = [original]

                character_profile = summarize_character(character_obj)
                history_text = format_history_for_audio(
                    history_list,
                    getattr(character_obj, 'name', None) if character_obj else None,
                    getattr(character_obj, 'persona', None) if character_obj else None,
                )

                if audio_cfg.get('dspy', {}).get('normalize', False):
                    try:
                        disfluency_module = get_audio_disfluency_module()
                        normalized = disfluency_module.normalize(
                            system_prompt=getattr(gemini_client, 'last_audio_system_prompt', getattr(gemini_client, 'last_audio_prompt', "")),
                            user_prompt=getattr(gemini_client, 'last_audio_user_prompt', ""),
                            conversation_history=history_text,
                            raw_transcription=transcription_json,
                            trace_id=trace_id,
                        )
                        normalized_json = normalized.get('normalized_json', transcription_json)
                        normalized_result = json.loads(normalized_json)
                        original = normalized_result.get('original', original)
                        options = normalized_result.get('options', options)
                    except Exception as norm_error:
                        logger.warning(
                            "DSPy audio normalize 失敗: trace_id=%s err=%s",
                            trace_id,
                            norm_error,
                        )

                return {
                    "raw_transcript": raw_transcript,
                    "keyword_completion": keyword_completion,
                    "original": original,
                    "options": options,
                    "trace_id": trace_id,
                    "character_profile": character_profile,
                    "history_text": history_text,
                }

            except json.JSONDecodeError:
                logger.error(f"無法解析識別結果 JSON: {transcription_json}")
                return {
                    "raw_transcript": "",
                    "keyword_completion": [],
                    "original": transcription_json,
                    "options": [transcription_json],
                    "trace_id": trace_id,
                }

        except Exception as e:
            logger.error(f"使用 Gemini 進行音頻識別時出錯: {e}", exc_info=True)
            return {
                "raw_transcript": "",
                "keyword_completion": [],
                "original": "識別失敗",
                "options": ["您好，這是一條測試訊息。目前遇到了語音識別問題，請稍後再試或改用文字輸入。"],
                "trace_id": trace_id,
            }
    
    except Exception as e:
        logger.error(f"音頻處理失敗: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"音頻處理失敗: {str(e)}"
        )
    
    finally:
        # 清理所有臨時文件
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"已刪除臨時文件: {temp_file}")
            except Exception as e:
                logger.warning(f"刪除臨時文件時出錯: {e}")

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
    session: Optional[Dict[str, Any]] = None,
    performance_metrics: Optional[Dict[str, Any]] = None,
    dialogue_manager: Optional[Any] = None
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
            "responses": [f"JSONDecodeError: {e}"],
            "state": "ERROR",
            "dialogue_context": "JSON_PARSE_ERROR",
            "error": {
                "type": "JSONDecodeError",
                "message": str(e)
            }
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
        logger.warning("回應中缺少 responses 鍵或為空")
        response_dict["responses"] = []

    if "state" not in response_dict:
        logger.warning("回應中缺少 state 鍵，使用默認值")
        response_dict["state"] = "UNKNOWN"

    if "dialogue_context" not in response_dict:
        logger.warning("回應中缺少 dialogue_context 鍵，使用默認值")
        response_dict["dialogue_context"] = ""

    # 規範化 responses：在非 optimized 實現下才執行深度規範化
    try:
        impl = session.get("implementation_version", "original") if session else "original"
        if impl != "optimized":
            res = response_dict.get("responses")
            if isinstance(res, list) and len(res) == 1 and isinstance(res[0], str):
                s = res[0].strip()
                if s.startswith('[') and s.endswith(']'):
                    parsed = None
                    try:
                        parsed = json.loads(s)
                    except json.JSONDecodeError:
                        import ast as _ast
                        try:
                            parsed = _ast.literal_eval(s)
                        except Exception:
                            parsed = None
                    if isinstance(parsed, list):
                        response_dict["responses"] = [str(x) for x in parsed[:5]]
            elif isinstance(res, str):
                s = res.strip()
                if s.startswith('[') and s.endswith(']'):
                    try:
                        parsed = json.loads(s)
                        if isinstance(parsed, list):
                            response_dict["responses"] = [str(x) for x in parsed[:5]]
                    except json.JSONDecodeError:
                        import ast as _ast
                        try:
                            parsed = _ast.literal_eval(s)
                            if isinstance(parsed, list):
                                response_dict["responses"] = [str(x) for x in parsed[:5]]
                        except Exception:
                            pass
                else:
                    lines = [line.strip() for line in s.split('\n') if line.strip()]
                    if lines:
                        response_dict["responses"] = lines[:5]
            if not isinstance(response_dict.get("responses"), list):
                response_dict["responses"] = [str(response_dict.get("responses"))] if response_dict.get("responses") is not None else []
            else:
                response_dict["responses"] = [str(x) for x in response_dict["responses"]]
            expanded = []
            for item in response_dict["responses"]:
                text = str(item)
                trimmed = text.strip()
                if trimmed.startswith('['):
                    candidate = trimmed
                    if not trimmed.endswith(']'):
                        closing = trimmed.rfind(']')
                        if closing != -1:
                            candidate = trimmed[:closing + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        import ast as _ast
                        try:
                            parsed = _ast.literal_eval(candidate)
                        except Exception:
                            parsed = None
                    if isinstance(parsed, list):
                        expanded.extend(str(x) for x in parsed)
                        remainder = trimmed[len(candidate):].strip()
                        if remainder:
                            expanded.append(remainder)
                        continue
                expanded.append(text)
            if expanded:
                response_dict["responses"] = expanded[:5]
    except Exception as _e:
        logger.warning(f"規範化 responses 失敗: {_e}")
    
    # Phase 5: 準備版本信息和性能指標
    implementation_version = "original"
    if session and "implementation_version" in session:
        implementation_version = session["implementation_version"]
    
    # 構建性能指標字典（如果有的話）
    metrics_dict = None
    if performance_metrics:
        metrics_dict = {
            "response_time": round(performance_metrics.duration, 3),
            "timestamp": performance_metrics.timestamp.isoformat(),
            "success": performance_metrics.success
        }
        
        # 如果是優化版本，添加 API 調用節省統計
        if implementation_version == "optimized" and hasattr(dialogue_manager, 'get_optimization_statistics'):
            try:
                opt_stats = dialogue_manager.get_optimization_statistics()
                metrics_dict.update({
                    "api_calls_saved": opt_stats.get('api_calls_saved', 0),
                    "efficiency_improvement": opt_stats.get('efficiency_summary', {}).get('efficiency_improvement', 'N/A'),
                    "conversations_processed": opt_stats.get('total_conversations', 0)
                })
            except Exception as e:
                logger.warning(f"無法獲取優化統計: {e}")
    
    # 構建回應對象
    try:
        response = DialogueResponse(
            status="success",
            responses=response_dict["responses"],
            state=response_dict["state"],
            dialogue_context=response_dict["dialogue_context"],
            session_id=current_session_id or str(uuid.uuid4()),
            inferred_speaker_role=response_dict.get("inferred_speaker_role"),  # 推理出的提問者角色
            speech_recognition_options=response_dict.get("speech_recognition_options", None),
            implementation_version=implementation_version,  # Phase 5: 版本信息
            performance_metrics=metrics_dict,  # Phase 5: 性能指標
            processing_info=response_dict.get("processing_info"),
            logs=(session or {}).get("logs") if session else None,
        )
        return response
    except Exception as e:
        logger.error(f"創建 DialogueResponse 時出錯: {e}", exc_info=True)
        return DialogueResponse(
            status="error",
            responses=[f"DialogueResponseError[{type(e).__name__}]: {e}"],
            state="ERROR",
            dialogue_context="DIALOGUE_RESPONSE_EXCEPTION",
            session_id=current_session_id or str(uuid.uuid4()),
            speech_recognition_options=None,
            implementation_version=implementation_version,
            performance_metrics=metrics_dict
        )

# 添加一個新函數創建對話管理器，並添加詳細日誌記錄
def create_dialogue_manager_with_monitoring(character: Character, log_dir: str = "logs/api", session_id: Optional[str] = None) -> tuple:
    """創建對話管理器並返回實現版本信息
    
    Args:
        character: 角色對象
        log_dir: 日誌目錄
    
    Returns:
        (DialogueManager 實例, 實現版本字符串)
    """
    logger.debug(f"創建對話管理器，角色: {character.name}, 類型: {type(character)}")
    # 使用 session 短ID 讓 dspy_debug 與 chat_gui 一一對應
    sess_short = (session_id or "")[:8] if session_id else ""
    tag = character.name if not sess_short else f"{character.name}_sess_{sess_short}"
    log_path = start_dspy_debug_log(tag=tag)
    if log_path:
        logger.info(f"已建立新的 DSPy 除錯日誌: {log_path}")
    try:
        # 使用工廠函數創建對話管理器（提供每會話專屬檔名前綴）
        from datetime import datetime as _dt
        ts = _dt.now().strftime('%Y%m%d_%H%M%S')
        base = f"{ts}_{character.name}"
        if sess_short:
            base = f"{base}_sess_{sess_short}"
        manager = create_dialogue_manager(character, use_terminal=False, log_dir=log_dir, log_file_basename=base)

        # 強制綁定 chat_gui 檔名，確保與 dspy_debug 一一對應（消除任何回退命名影響）
        try:
            chat_dir = log_dir
            os.makedirs(chat_dir, exist_ok=True)
            chat_filename = f"{base}_chat_gui.log"
            manager.log_filename = chat_filename
            manager.log_filepath = os.path.join(chat_dir, chat_filename)
            logger.info(f"已設定會話專屬 chat_gui 檔案: {manager.log_filepath}")
        except Exception as _e:
            logger.warning(f"設定 chat_gui 檔名失敗（將使用預設）: {_e}")
        
        # 檢測實現版本
        implementation_version = "original"
        if hasattr(manager, 'optimization_enabled') and manager.optimization_enabled:
            implementation_version = "optimized"
        elif hasattr(manager, 'dspy_enabled') and manager.dspy_enabled:
            implementation_version = "dspy"
        
        logger.info(f"成功創建對話管理器: {type(manager).__name__} (版本: {implementation_version})")
        return manager, implementation_version, log_path
    except Exception as e:
        logger.error(f"創建對話管理器失敗: {e}", exc_info=True)
        raise

# Phase 5: 性能監控端點
@app.get("/api/monitor/stats")
async def get_performance_stats():
    """獲取性能統計數據"""
    try:
        performance_monitor = get_performance_monitor()
        current_stats = performance_monitor.get_current_stats()
        
        return {
            "status": "success",
            "stats": {
                implementation: {
                    "total_requests": stats.total_requests,
                    "successful_requests": stats.successful_requests,
                    "failed_requests": stats.failed_requests,
                    "avg_response_time": round(stats.avg_response_time, 3),
                    "error_rate": round(stats.error_rate * 100, 2),  # 轉為百分比
                    "last_updated": stats.last_updated.isoformat()
                }
                for implementation, stats in current_stats.items()
            }
        }
    except Exception as e:
        logger.error(f"獲取性能統計失敗: {e}")
        raise HTTPException(status_code=500, detail=f"統計數據獲取失敗: {str(e)}")

@app.get("/api/monitor/comparison")
async def get_comparison_report():
    """獲取 DSPy vs 原始實現對比報告"""
    try:
        performance_monitor = get_performance_monitor()
        comparison_report = performance_monitor.get_comparison_report()
        
        return {
            "status": "success",
            "report": comparison_report
        }
    except Exception as e:
        logger.error(f"獲取對比報告失敗: {e}")
        raise HTTPException(status_code=500, detail=f"對比報告獲取失敗: {str(e)}")

@app.get("/api/monitor/errors")
async def get_error_summary(hours: int = 24):
    """獲取錯誤摘要"""
    try:
        performance_monitor = get_performance_monitor()
        error_summary = performance_monitor.get_error_summary(hours=hours)
        
        return {
            "status": "success",
            "time_range_hours": hours,
            "errors": error_summary
        }
    except Exception as e:
        logger.error(f"獲取錯誤摘要失敗: {e}")
        raise HTTPException(status_code=500, detail=f"錯誤摘要獲取失敗: {str(e)}")


@app.post("/api/debug/start-log")
async def start_dspy_debug_log_api(tag: Optional[str] = None):
    """Start a new DSPy debug log file and return the path."""
    path = start_dspy_debug_log(tag=tag)
    if path is None:
        raise HTTPException(status_code=500, detail="無法重新建立 DSPy 除錯日誌檔案")

    return {
        "status": "success",
        "log_path": str(path)
    }

@app.post("/api/monitor/reset")
async def reset_performance_stats():
    """重置性能統計數據"""
    try:
        performance_monitor = get_performance_monitor()
        performance_monitor.reset_stats()
        
        return {
            "status": "success",
            "message": "性能統計數據已重置"
        }
    except Exception as e:
        logger.error(f"重置統計數據失敗: {e}")
        raise HTTPException(status_code=500, detail=f"重置失敗: {str(e)}")

# Characters endpoint
@app.get("/api/characters")
async def get_characters():
    """獲取可用角色列表"""
    try:
        characters_file = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'characters.yaml')
        
        with open(characters_file, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            characters = data.get('characters', {})
            
        return {
            "status": "success",
            "characters": {
                char_id: {
                    "name": char_data.get("name", f"Character {char_id}"),
                    "persona": char_data.get("persona", ""),
                    "backstory": char_data.get("backstory", "")[:100] + "..." if len(char_data.get("backstory", "")) > 100 else char_data.get("backstory", "")
                }
                for char_id, char_data in characters.items()
            }
        }
        
    except FileNotFoundError:
        logger.error("characters.yaml 文件未找到")
        return {
            "status": "success", 
            "characters": {
                "1": {
                    "name": "Patient 1",
                    "persona": "一般病患",
                    "backstory": "系統默認角色"
                }
            }
        }
    except Exception as e:
        logger.error(f"獲取角色列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"角色列表獲取失敗: {str(e)}")

# Phase 5: 健康監控和回退端點
@app.get("/api/health/status")
async def get_health_status():
    """獲取系統健康狀況"""
    try:
        health_monitor = get_health_monitor()
        performance_monitor = get_performance_monitor()
        
        # 執行健康檢查
        health_statuses = health_monitor.check_health(performance_monitor)
        monitor_status = health_monitor.get_status()
        
        return {
            "status": "success",
            "health_statuses": {
                implementation: {
                    "is_healthy": status.is_healthy,
                    "error_rate": round(status.error_rate * 100, 2),
                    "avg_response_time": round(status.avg_response_time, 3),
                    "recent_errors": status.recent_errors,
                    "issues": status.issues,
                    "last_check": status.last_check.isoformat()
                }
                for implementation, status in health_statuses.items()
            },
            "monitor_status": monitor_status
        }
    except Exception as e:
        logger.error(f"獲取健康狀況失敗: {e}")
        raise HTTPException(status_code=500, detail=f"健康檢查失敗: {str(e)}")

@app.post("/api/health/fallback")
async def manual_fallback(request: dict = Body(...)):
    """手動觸發或停用回退機制"""
    try:
        enable = request.get("enable", False)
        reason = request.get("reason", "手動操作")
        
        health_monitor = get_health_monitor()
        success = health_monitor.manual_fallback(enable, reason)
        
        if success:
            return {
                "status": "success",
                "message": f"回退機制已{'啟用' if enable else '停用'}",
                "reason": reason
            }
        else:
            raise HTTPException(status_code=500, detail="回退操作失敗")
            
    except Exception as e:
        logger.error(f"手動回退操作失敗: {e}")
        raise HTTPException(status_code=500, detail=f"回退操作失敗: {str(e)}")

@app.post("/api/health/thresholds")
async def update_health_thresholds(request: dict = Body(...)):
    """更新健康檢查閾值"""
    try:
        thresholds = request.get("thresholds", {})
        
        health_monitor = get_health_monitor()
        success = health_monitor.update_thresholds(thresholds)
        
        if success:
            return {
                "status": "success",
                "message": "健康檢查閾值已更新",
                "updated_thresholds": thresholds
            }
        else:
            raise HTTPException(status_code=500, detail="閾值更新失敗")
            
    except Exception as e:
        logger.error(f"更新健康檢查閾值失敗: {e}")
        raise HTTPException(status_code=500, detail=f"閾值更新失敗: {str(e)}")

# API 路由
@app.post("/api/dialogue/text", response_model=DialogueResponse)
async def process_text_dialogue(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict = Body(
        ...,  # Ellipsis 表示必填
        example={}
    )
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
        #body = await request.json()
        logger.debug(f"解析後的請求體: {body}")
        
        # 創建請求模型
        text = body.get("text", "")
        character_id = body.get("character_id")
        session_id = body.get("session_id")
        character_config = body.get("character_config")  # 提取客戶端提供的角色配置
        
        logger.debug(f"提取參數: text={text}, character_id={character_id}, session_id={session_id}, character_config={'提供' if character_config else '未提供'}")
        
        # 檢查 character_config 是否為字符串，若是則嘗試解析為字典
        if character_config and isinstance(character_config, str):
            try:
                #logger.debug(f"\n\ncharacter_config:\n{character_config}\n\n")
                logger.info("process_text_dialogue: character_config 是字符串，嘗試解析為 JSON")
                character_config = json.loads(character_config)
                logger.info("process_text_dialogue: 成功將 character_config 字符串解析為字典")
            except json.JSONDecodeError as e:
                logger.error(f"process_text_dialogue: 解析 character_config 字符串失敗: {e}")
                # 繼續處理，get_or_create_session 會處理解析問題
        
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
                logger.debug("嘗試創建新會話")
                session = await get_or_create_session(
                    request=request,
                    character_id=character_id,
                    character_config=character_config
                )
                session_id = next(key for key, value in session_store.items() if value is session)
                logger.debug(f"成功創建新會話，ID: {session_id}")
            except Exception as e:
                logger.error(f"創建會話時出錯: {e}", exc_info=True)
                # 記錄詳細的堆疊跟踪
                logger.error(f"詳細錯誤堆疊: {traceback.format_exc()}")
                raise HTTPException(
                    status_code=500,
                    detail=f"創建會話失敗: {str(e)}"
                )
        
        # 在調用對話管理器前添加診斷信息
        logger.debug(f"使用的角色信息: id={character_id}, name={session['dialogue_manager'].character.name}")
        
        # Phase 5: 性能監控 - 開始請求追蹤
        performance_monitor = get_performance_monitor()
        implementation_version = session.get("implementation_version", "unknown")
        monitoring_context = performance_monitor.start_request(
            implementation=implementation_version,
            endpoint="text_dialogue",
            character_id=character_id,
            session_id=session_id
        )
        
        try:
            # 調用對話管理器處理用戶輸入
            dialogue_manager = session["dialogue_manager"]
            logger.debug(f"調用對話管理器處理: '{text}' (實現版本: {implementation_version})")
            
            # 直接使用對話管理器處理
            response_json = await dialogue_manager.process_turn(text)
            logger.debug(f"對話管理器返回結果: {response_json}")
            
            # Phase 5: 性能監控 - 記錄成功
            performance_metrics = performance_monitor.end_request(
                context=monitoring_context,
                success=True,
                response_length=len(str(response_json))
            )
            
        except Exception as e:
            logger.error(f"對話管理器處理輸入時出錯: {e}", exc_info=True)
            # 記錄詳細的堆疊跟踪
            logger.error(f"詳細錯誤堆疊: {traceback.format_exc()}")
            
            # Phase 5: 性能監控 - 記錄失敗
            performance_monitor.end_request(
                context=monitoring_context,
                success=False,
                error_message=str(e)
            )
            
            raise HTTPException(
                status_code=500,
                detail=f"對話處理失敗: {str(e)}"
            )
        
        # 排程清理舊會話
        background_tasks.add_task(cleanup_old_sessions, background_tasks)
        
        # 使用輔助函數格式化回應
        try:
            response = await format_dialogue_response(
                response_json=response_json,
                session_id=session_id,
                session=session,
                performance_metrics=performance_metrics,  # Phase 5: 傳遞性能指標
                dialogue_manager=dialogue_manager  # 傳遞對話管理器以獲取優化統計
            )
            logger.debug(f"返回回應: {response} (版本: {implementation_version})")
        except Exception as e:
            logger.error(f"格式化回應時出錯: {e}", exc_info=True)
            # 記錄詳細的堆疊跟踪
            logger.error(f"詳細錯誤堆疊: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"格式化回應失敗: {str(e)}"
            )
        
        # 直接返回文本回應
        return response
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析錯誤: {e}")
        logger.error(f"詳細錯誤堆疊: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"無效的 JSON 格式: {str(e)}")
    except Exception as e:
        logger.error(f"處理文本對話請求時出錯: {e}", exc_info=True)
        logger.error(f"詳細錯誤堆疊: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"處理請求時發生錯誤: {str(e)}")

@app.post("/api/dialogue/audio", response_model=DialogueResponse)
async def process_audio_dialogue(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    character_id: str = Form(...),
    session_id: Optional[str] = Form(None),
    response_format: Optional[str] = Form("text"),  # 回覆格式，默認為文本
    character_config_json: Optional[str] = Form(None),  # 新增：角色配置 JSON 字符串
):
    """處理音頻對話請求

    Args:
        request: 原始請求對象
        background_tasks: FastAPI 背景任務
        audio_file: 上傳的音頻文件
        character_id: 角色ID
        session_id: 會話ID (可選)
        response_format: 回覆格式 (可選值: "text" 或 "audio")
        character_config_json: 角色配置的 JSON 字符串 (可選)

    Returns:
        對話回應
    """
    logger.debug(f"處理音頻對話請求: character_id={character_id}, session_id={session_id}, character_config_json={'提供' if character_config_json else '未提供'}")
    
    # 解析角色配置 JSON 字符串
    character_config = None
    if character_config_json:
        try:
            character_config = json.loads(character_config_json)
            logger.debug(f"已解析角色配置 JSON: {json.dumps(character_config, ensure_ascii=False, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"角色配置 JSON 解析錯誤: {e}")
            # 不要直接中斷，嘗試使用原始字符串
            logger.info("使用原始字符串作為 character_config，讓 get_or_create_session 處理")
            character_config = character_config_json
    
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
            logger.debug(f"已創建新會話: {session_id}")
        except Exception as e:
            logger.error(f"創建會話時出錯: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"創建會話失敗: {str(e)}"
            )
    
    # 語音轉文本（傳入當前會話以便注入角色與歷史）
    text_result = await speech_to_text(
        audio_file,
        dialogue_manager=session["dialogue_manager"],
        session_id=session_id,
    )
    logger.debug(f"音頻識別結果: {text_result}")
    
    # 處理返回結果（可能是字典或JSON字符串）
    if isinstance(text_result, dict):
        # 已經是字典，直接使用
        text_dict = text_result
        logger.debug("speech_to_text 返回了字典對象")
    else:
        # 嘗試解析 JSON 字符串
        try:
            text_dict = json.loads(text_result)
            logger.debug("成功將 speech_to_text 返回的 JSON 字符串解析為字典")
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"無法解析音頻識別結果: {e}")
            # 使用預設值
            text_dict = {
                "original": str(text_result),
                "options": [str(text_result)]
            }
            logger.debug(f"使用預設字典: {text_dict}")
    
    # 提取原始文本和選項（包含 self-annotation 欄位）
    raw_transcript = text_dict.get("raw_transcript", "")
    keyword_completion = text_dict.get("keyword_completion", [])
    original_text = text_dict.get("original", "")
    options_list = text_dict.get("options", [])

    # 確保選項是有效的列表
    if not isinstance(options_list, list) or not options_list:
        logger.warning("識別選項無效或為空，使用原始文本作為選項")
        options_list = [original_text] if original_text else ["無法識別您的語音"]

    logger.info(f"原始轉錄片段: '{raw_transcript}'")
    logger.info(f"原始識別文本: '{original_text}'")
    logger.info(f"識別選項 ({len(options_list)}): {options_list}")
    
    # 將語音識別選項和狀態保存在 DialogueManager 中，供選擇回應時使用
    dialogue_manager = session["dialogue_manager"]
    if not hasattr(dialogue_manager, 'last_speech_options'):
        dialogue_manager.last_speech_options = []
    dialogue_manager.last_speech_options = options_list
    
    if not hasattr(dialogue_manager, 'last_response_state'):
        dialogue_manager.last_response_state = ""
    dialogue_manager.last_response_state = "WAITING_SELECTION"
    
    # 僅儲存「病患自己的話」到對話歷史：將原始識別文本作為病患發言
    try:
        patient_name = getattr(dialogue_manager.character, 'name', '病患')
        orig = (original_text or '').strip()
        if orig and not orig.startswith("無法識別") and orig != "識別失敗":
            dialogue_manager.conversation_history.append(f"{patient_name}: {orig}")
    except Exception:
        # 若歷史寫入失敗則忽略，不影響主流程
        pass
    
    # 獲取實現版本信息
    implementation_version = "original"
    if session and "implementation_version" in session:
        implementation_version = session["implementation_version"]
    
    # 創建基本的性能指標（音頻識別過程中的指標）
    audio_metrics = None
    if session and session.get("last_performance_metrics"):
        last_metrics = session["last_performance_metrics"]
        audio_metrics = {
            "response_time": round(last_metrics.duration, 3) if hasattr(last_metrics, 'duration') else 0,
            "timestamp": last_metrics.timestamp.isoformat() if hasattr(last_metrics, 'timestamp') else datetime.now().isoformat(),
            "success": True,
            "audio_processing": True
        }
    
    # 創建回應
    response = DialogueResponse(
        status="success",
        responses=["請從以下選項中選擇您想表達的內容:"],
        state="WAITING_SELECTION",
        dialogue_context="語音選項選擇",
        session_id=session_id,
        speech_recognition_options=options_list,
        original_transcription=original_text or None,
        raw_transcript=raw_transcript or None,
        keyword_completion=keyword_completion or None,
        implementation_version=implementation_version,
        performance_metrics=audio_metrics,
        logs=session.get("logs") if session else None,
    )

    # 保存語音識別選項到交互日誌（包含 self-annotation 欄位）
    dialogue_manager.log_interaction(
        user_input="[語音輸入]",
        response_options=options_list,
        selected_response=None,
        raw_transcript=raw_transcript,
        keyword_completion=keyword_completion
    )
    
    # 排程清理舊會話
    background_tasks.add_task(cleanup_old_sessions, background_tasks)
    
    logger.debug(f"返回語音識別選項: {response}")
    
    # 直接返回文本回應
    return response

@app.post("/api/dialogue/audio_input", response_model=DialogueResponse)
async def process_audio_input_dialogue(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    character_id: str = Form(...),
    session_id: Optional[str] = Form(None),
    character_config_json: Optional[str] = Form(None), 
):
    """處理音頻輸入對話請求 (Gemini 直接轉錄 + 對話)"""
    logger.debug(f"Processing audio input dialogue request (gemini): character_id={character_id}, session_id={session_id}, character_config_json={'provided' if character_config_json else 'not provided'}")

    # 解析角色配置 JSON
    character_config = None
    if character_config_json:
        try:
            character_config = json.loads(character_config_json)
            logger.debug(f"Parsed character_config_json: keys={list(character_config.keys()) if isinstance(character_config, dict) else 'N/A'}")
        except json.JSONDecodeError:
            logger.warning("Invalid character_config_json format, ignoring it")
            character_config = None

    # 會話管理
    try:
        if session_id and session_id in session_store:
            session = session_store[session_id]
            session["last_activity"] = asyncio.get_event_loop().time()
        else:
            session_obj = await get_or_create_session(
                request=request,
                session_id=session_id,
                character_id=character_id,
                character_config=character_config
            )
            # 取得新 session_id
            if not session_id:
                for sid, sdata in session_store.items():
                    if sdata is session_obj:
                        session_id = sid
                        break
            session = session_obj
    except Exception as e:
        logger.error(f"Session management error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Session error: {str(e)}")

    # 保存音頻到臨時檔
    temp_audio_file_path: Optional[str] = None
    try:
        # 從文件名獲取擴展名
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        if not file_ext:
            file_ext = '.wav'  # 默認擴展名
        
        # 使用原始擴展名創建臨時文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_audio_file:
            content = await audio_file.read()
            tmp_audio_file.write(content)
            temp_audio_file_path = tmp_audio_file.name
        logger.debug(f"Saved temp audio file: {temp_audio_file_path} (format: {file_ext})")
    except Exception as e:
        logger.error(f"Failed saving uploaded audio: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to save audio file: {str(e)}")

    # Gemini 轉錄
    try:
        from ..llm.gemini_client import GeminiClient
        
        gemini_client = GeminiClient()
        
        # 嘗試從 session 中獲取上下文以增強識別準確度
        dm = session.get("dialogue_manager") if session else None
        character_obj = getattr(dm, 'character', None) if dm else None
        history_list = getattr(dm, 'conversation_history', None) if dm else None
        
        transcription_json = gemini_client.transcribe_audio(
            temp_audio_file_path,
            character=character_obj,
            conversation_history=history_list,
            session_id=session_id
        )
        try:
            transcription = json.loads(transcription_json)
        except json.JSONDecodeError:
            transcription = {"original": transcription_json, "options": [transcription_json]}
        options = transcription.get("options") or []
        original_text = transcription.get("original") or (options[0] if options else "")
        text_input = original_text 
        if not text_input:
            raise HTTPException(status_code=400, detail="Unable to transcribe audio")
        logger.info(f"Gemini transcription selected text: '{text_input}' (options={len(options)})")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gemini transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

    # Phase 5: 音頻對話性能監控
    performance_monitor = get_performance_monitor()
    implementation_version = session.get("implementation_version", "unknown")
    monitoring_context = performance_monitor.start_request(
        implementation=implementation_version,
        endpoint="audio_dialogue",
        character_id=character_id,
        session_id=session_id
    )
    
    # Dialogue processing
    try:
        dialogue_manager = session["dialogue_manager"]
        response_json = await dialogue_manager.process_turn(text_input)
        
        # Phase 5: 記錄成功
        performance_metrics = performance_monitor.end_request(
            context=monitoring_context,
            success=True,
            response_length=len(str(response_json))
        )
        
    except Exception as e:
        logger.error(f"Dialogue processing failed: {e}", exc_info=True)
        
        # Phase 5: 記錄失敗
        performance_monitor.end_request(
            context=monitoring_context,
            success=False,
            error_message=str(e)
        )
        
        raise HTTPException(status_code=500, detail=f"Dialogue error: {str(e)}")

    # 格式化回應
    try:
        formatted_response = await format_dialogue_response(
            response_json=response_json,
            session_id=session_id,
            session=session,
            performance_metrics=performance_metrics,  # Phase 5: 傳遞性能指標
            dialogue_manager=dialogue_manager  # 傳遞對話管理器以獲取優化統計
        )
        # 附加候選選項供前端參考（仍為直接模式，不要求再選）
        if options:
            formatted_response.speech_recognition_options = options
        # 加入原始轉錄文本
        formatted_response.original_transcription = original_text or None
        background_tasks.add_task(cleanup_old_sessions, background_tasks)
        return formatted_response
    except Exception as e:
        logger.error(f"Formatting response failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Formatting error: {str(e)}")
    finally:
        if temp_audio_file_path and os.path.exists(temp_audio_file_path):
            try:
                os.remove(temp_audio_file_path)
                logger.debug(f"Deleted temp audio file: {temp_audio_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp audio file {temp_audio_file_path}: {e}")

@app.post("/api/dialogue/select_response")
async def select_response(request: SelectResponseRequest):
    """處理患者選擇的回應
    
    Args:
        request: 包含會話ID和選擇的回應
        
    Returns:
        成功或失敗的狀態
    """
    logger.debug(f"處理選擇回應請求: session_id={request.session_id}, selected_response='{request.selected_response}'")
    
    # 檢查會話是否存在
    if request.session_id not in session_store:
        logger.error(f"找不到指定的會話: {request.session_id}")
        raise HTTPException(status_code=404, detail="找不到指定的會話")
    
    # 獲取會話
    session = session_store[request.session_id]
    
    # 更新會話活動時間
    session["last_activity"] = asyncio.get_event_loop().time()
    
    try:
        # 將選擇的回應添加到對話歷史
        dialogue_manager = session["dialogue_manager"]
        
        # 檢查對話歷史中的最後一個狀態是否為等待選擇狀態
        # 使用更可靠的檢測方法，檢查會話屬性而非文本匹配
        is_after_speech_recognition = False
        
        # 1. 檢查是否有語音識別標記
        if hasattr(dialogue_manager, 'last_response_state') and dialogue_manager.last_response_state == "WAITING_SELECTION":
            is_after_speech_recognition = True
            logger.debug("檢測到語音識別狀態標記: WAITING_SELECTION")
        
        # 2. 檢查對話日誌中是否有語音識別選項記錄
        if hasattr(dialogue_manager, 'interaction_log') and dialogue_manager.interaction_log:
            latest_entries = dialogue_manager.interaction_log[-3:]  # 檢查最近的3個記錄
            for entry in latest_entries:
                if isinstance(entry, dict) and 'speech_recognition_options' in entry and entry['speech_recognition_options']:
                    is_after_speech_recognition = True
                    logger.debug("檢測到語音識別選項記錄")
                    break
        
        # 3. 檢查選擇的回應是否在最近的語音識別選項列表中
        if hasattr(dialogue_manager, 'last_speech_options') and dialogue_manager.last_speech_options:
            # 檢查部分匹配，因為選項可能有些微差異
            for option in dialogue_manager.last_speech_options:
                if option in request.selected_response or request.selected_response in option:
                    is_after_speech_recognition = True
                    logger.debug(f"選擇的回應與語音選項匹配: {option}")
                    break
        
        # 4. 直接檢查對話內容中的標記或關鍵詞
        last_entries = dialogue_manager.conversation_history[-3:]  # 檢查最近的3個對話
        for entry in last_entries:
            if "語音輸入" in entry or "請從以下選項中選擇" in entry or "語音識別" in entry:
                is_after_speech_recognition = True
                logger.debug(f"從對話內容檢測到語音識別相關標記: {entry}")
                break
        
        # 記錄到對話歷史
        dialogue_manager.conversation_history.append(f"{dialogue_manager.character.name}: {request.selected_response}")
        
        # 記錄選擇的回應
        dialogue_manager.log_interaction(
            user_input="",  # 空，因為這只是回應選擇
            response_options=[],  # 空，因為選項已經在之前的請求中記錄
            selected_response=request.selected_response
        )
        
        # 保存交互日誌
        dialogue_manager.save_interaction_log()
        
        # 如果這是語音識別後的選擇，不需要向 Gemini API 發送請求
        if is_after_speech_recognition:
            logger.info(f"這是語音識別後的選擇，跳過 Gemini API 處理: {request.selected_response}")
            
            # 清除語音識別的狀態標記(如果有)
            if hasattr(dialogue_manager, 'last_response_state'):
                dialogue_manager.last_response_state = "NORMAL"
            if hasattr(dialogue_manager, 'last_speech_options'):
                dialogue_manager.last_speech_options = []
            
            # 直接返回成功訊息，不包含回應
            return {
                "status": "success", 
                "message": "語音識別選擇已記錄",
                "responses": ["已記錄您的選擇"],
                "state": "NORMAL",
                "dialogue_context": "語音識別選擇完成"
            }
        
        # Phase 5: 選擇回應性能監控
        performance_monitor = get_performance_monitor()
        implementation_version = session.get("implementation_version", "unknown")
        character_id = session.get("character_id", "unknown")
        monitoring_context = performance_monitor.start_request(
            implementation=implementation_version,
            endpoint="select_response",
            character_id=character_id,
            session_id=request.session_id
        )
        
        # 如果不是語音識別後的選擇，正常處理
        logger.info(f"處理選擇的回應，發送到 Gemini API: {request.selected_response}")
        try:
            response_json = await dialogue_manager.process_turn(request.selected_response)
            
            # Phase 5: 記錄成功
            performance_metrics = performance_monitor.end_request(
                context=monitoring_context,
                success=True,
                response_length=len(str(response_json))
            )
            
        except Exception as e:
            # Phase 5: 記錄失敗
            performance_monitor.end_request(
                context=monitoring_context,
                success=False,
                error_message=str(e)
            )
            raise
        
        logger.debug(f"成功記錄選擇的回應: {request.selected_response}")
        logger.debug(f"對話管理器處理結果: {response_json}")
        
        # 構建具有處理結果的回應
        response_dict = json.loads(response_json)
        return {
            "status": "success", 
            "message": "回應選擇已記錄",
            "responses": response_dict.get("responses", []),
            "state": response_dict.get("state", "NORMAL"),
            "dialogue_context": response_dict.get("dialogue_context", "一般對話")
        }
    
    except Exception as e:
        logger.error(f"處理選擇回應時出錯: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"處理選擇回應時出錯: {str(e)}")


# 如果直接運行此模塊，啟動服務器
if __name__ == "__main__":
    # 啟動前清理角色和會話緩存
    character_cache.clear()
    session_store.clear()
    logger.info("已清理角色和會話緩存，啟動服務器...")
    
    # 啟動服務器
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True) 
