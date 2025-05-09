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


import numpy as np
from scipy.io import wavfile

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
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
    speech_recognition_options: Optional[List[str]] = None  # 新增: 語音識別可能的選項

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
async def speech_to_text(audio_file: UploadFile) -> Dict[str, Any]:
    """將上傳的音頻文件轉換為文本，並提供多個可能的完整句子選項

    Args:
        audio_file: 上傳的音頻文件

    Returns:
        包含原始識別和多個選項的字典
    """
    logger.debug(f"開始處理音頻文件: {audio_file.filename}")
    
    temp_files = []  # 追蹤需要刪除的臨時文件
    
    try:
        # 保存上傳的文件
        original_audio_path = f"temp_audio_{uuid.uuid4()}.wav"
        temp_files.append(original_audio_path)
        
        with open(original_audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        logger.debug(f"已保存臨時文件: {original_audio_path}")
        
        # 導入音頻處理工具
        from ..utils.audio_processor import check_audio_format, preprocess_audio
        
        # 檢查音頻格式
        if not check_audio_format(original_audio_path):
            logger.warning(f"上傳的音頻格式無效或不是WAV格式: {original_audio_path}")
            return {
                "original": "音頻格式無效",
                "options": ["您好，上傳的音頻格式無效。請使用WAV格式錄音。"]
            }
        
        # 預處理音頻以優化識別
        processed_audio_path = f"processed_audio_{uuid.uuid4()}.wav"
        temp_files.append(processed_audio_path)
        
        processed_audio_path = preprocess_audio(
            input_file=original_audio_path,
            output_file=processed_audio_path
        )
        logger.debug(f"音頻預處理完成: {processed_audio_path}")
        
        # 使用 GeminiClient 進行語音識別
        try:
            from ..llm.gemini_client import GeminiClient
            import json
            
            # 初始化 GeminiClient
            gemini_client = GeminiClient()
            
            # 調用音頻識別方法，使用處理後的音頻
            logger.info(f"使用 Gemini 進行音頻識別: {processed_audio_path}")
            transcription_json = gemini_client.transcribe_audio(processed_audio_path)
            
            # 解析識別結果 JSON
            try:
                result = json.loads(transcription_json)
                
                # 提取原始識別和選項
                original = result.get("original", "")
                options = result.get("options", [])
                
                logger.info(f"音頻識別成功: 原始='{original}', 選項數={len(options)}")
                
                # 檢查識別結果
                if not original or original.startswith("無法識別") or original.startswith("音頻識別過程中發生錯誤"):
                    logger.warning(f"音頻識別失敗或沒有識別出有效內容: {original}")
                    # 使用一個友好的回退消息
                    return {
                        "original": original,
                        "options": ["您好，我沒能清楚聽到您的問題。請問您能再說一次嗎？"]
                    }
                
                # 如果沒有生成選項或選項數量太少，則使用原始識別作為選項
                if not options or len(options) < 1:
                    options = [original]
                
                # 返回識別結果
                return {
                    "original": original,
                    "options": options
                }
                
            except json.JSONDecodeError:
                logger.error(f"無法解析識別結果 JSON: {transcription_json}")
                return {
                    "original": transcription_json,
                    "options": [transcription_json]
                }
            
        except Exception as e:
            logger.error(f"使用 Gemini 進行音頻識別時出錯: {e}", exc_info=True)
            # 如果 Gemini 識別失敗，使用一個預設文本作為回退
            return {
                "original": "識別失敗",
                "options": ["您好，這是一條測試訊息。目前遇到了語音識別問題，請稍後再試或改用文字輸入。"]
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
            session_id=current_session_id or str(uuid.uuid4()),
            speech_recognition_options=response_dict.get("speech_recognition_options", None)
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
            session_id=current_session_id or str(uuid.uuid4()),
            speech_recognition_options=None
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
        
        try:
            # 調用對話管理器處理用戶輸入
            dialogue_manager = session["dialogue_manager"]
            logger.debug(f"調用對話管理器處理: '{text}'")
            
            # 直接使用對話管理器處理
            response_json = await dialogue_manager.process_turn(text)
            logger.debug(f"對話管理器返回結果: {response_json}")
        except Exception as e:
            logger.error(f"對話管理器處理輸入時出錯: {e}", exc_info=True)
            # 記錄詳細的堆疊跟踪
            logger.error(f"詳細錯誤堆疊: {traceback.format_exc()}")
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
                session=session
            )
            logger.debug(f"返回回應: {response}")
        except Exception as e:
            logger.error(f"格式化回應時出錯: {e}", exc_info=True)
            # 記錄詳細的堆疊跟踪
            logger.error(f"詳細錯誤堆疊: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"格式化回應失敗: {str(e)}"
            )
        
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
            raise HTTPException(status_code=400, detail=f"無效的角色配置 JSON: {str(e)}")
    
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
    
    # 語音轉文本
    text_dict = await speech_to_text(audio_file)
    logger.debug(f"音頻已轉換為文本: {text_dict}")
    
    # 提取原始文本和選項
    original_text = text_dict.get("original", "")
    text_options = text_dict.get("options", [])
    
    if not text_options:
        text_options = [original_text]
    
    # 調用對話管理器處理用戶輸入
    dialogue_manager = session["dialogue_manager"]
    logger.debug(f"調用對話管理器處理音頻轉換文本: '{original_text}'")
    response_json = await dialogue_manager.process_turn(original_text)
    
    # 排程清理舊會話
    background_tasks.add_task(cleanup_old_sessions, background_tasks)
    
    # 使用輔助函數格式化回應
    response = await format_dialogue_response(
        response_json=response_json,
        session_id=session_id,
        session=session
    )
    
    # 添加語音識別選項到回應
    if hasattr(response, "speech_recognition_options") and text_options:
        response.speech_recognition_options = text_options
    elif text_options:
        # 如果響應對象沒有此屬性，我們需要臨時添加這些選項到響應中
        response_dict = response.dict()
        response_dict["speech_recognition_options"] = text_options
        
        # 使用字典創建新的響應對象
        response = DialogueResponse(**response_dict)
    
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
        # 添加識別選項到響應頭
        if text_options:
            response.headers["X-Speech-Options"] = json.dumps(text_options)
        return response
    else:
        # 返回正常的文本回覆
        return response

@app.get("/api/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "ok", "active_sessions": len(session_store)}

# 添加一個簡單的 dummy TTS 函數
def dummy_tts(text: str) -> str:
    """模擬文本轉語音功能，生成測試用的音頻文件

    Args:
        text: 要轉換為語音的文本

    Returns:
        生成的音頻文件路徑
    """
    logger.debug(f"生成測試音頻文件，文本: '{text}'")
    
    try:
        # 創建一個簡單的 WAV 文件
        # 16kHz 採樣率，單聲道，16 位整數
        sample_rate = 16000
        duration = min(2 + len(text) * 0.05, 10)  # 根據文本長度調整，最長10秒
        
        # 產生數據，使用簡單的正弦波
        t = np.arange(0, duration, 1/sample_rate)
        frequency = 440  # A4 音符的頻率
        amplitude = 32767 * 0.5  # 16 位整數的一半振幅
        
        # 生成正弦波
        audio = np.sin(2 * np.pi * frequency * t) * amplitude
        audio = audio.astype(np.int16)  # 轉換為 16 位整數
        
        # 創建臨時文件
        output_path = f"temp_tts_{uuid.uuid4()}.wav"
        
        # 保存為 WAV 文件
        from scipy.io import wavfile
        wavfile.write(output_path, sample_rate, audio)
        
        logger.debug(f"已生成測試音頻文件: {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"生成測試音頻文件失敗: {e}", exc_info=True)
        # 如果出錯，創建一個空音頻文件
        output_path = f"empty_tts_{uuid.uuid4()}.wav"
        
        # 創建 1 秒鐘的靜音
        sample_rate = 16000
        silence = np.zeros(sample_rate, dtype=np.int16)
        
        from scipy.io import wavfile
        wavfile.write(output_path, sample_rate, silence)
        
        logger.warning(f"由於錯誤，創建了空白音頻文件: {output_path}")
        return output_path

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
        
        # 記錄到對話歷史（假設最後一輪對話還沒有回應）
        dialogue_manager.conversation_history.append(f"{dialogue_manager.character.name}: {request.selected_response}")
        
        # 記錄選擇的回應
        dialogue_manager.log_interaction(
            user_input="",  # 空，因為這只是回應選擇
            response_options=[],  # 空，因為選項已經在之前的請求中記錄
            selected_response=request.selected_response
        )
        dialogue_manager.save_interaction_log()
        
        logger.debug(f"成功記錄選擇的回應: {request.selected_response}")
        return {"status": "success", "message": "回應選擇已記錄"}
    
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