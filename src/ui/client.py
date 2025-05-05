import requests
import json
import os
import tempfile
from typing import Dict, Optional, List, Any, Tuple
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ui_client")

class ApiClient:
    """API 客戶端，用於與對話系統 API 通信"""
    
    def __init__(self, base_url: str = "http://120.126.51.6:8000"):
        """初始化 API 客戶端
        
        Args:
            base_url: API 服務器的基礎 URL
        """
        self.base_url = base_url
        self.session_id = None
        self.character_id = None
    
    def get_characters(self) -> List[Dict[str, Any]]:
        """獲取可用角色列表
        
        Returns:
            角色列表
        """
        try:
            url = f"{self.base_url}/api/characters"
            logger.info(f"正在從 {url} 獲取角色列表")
            
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"API 返回數據: {data}")
            
            characters = data.get("characters", [])
            
            # 確保返回的數據格式正確
            if not characters or not isinstance(characters, list):
                logger.warning("未獲取到角色或格式不正確，使用默認角色")
                return [{"id": "1", "name": "默認病患"}]
            
            # 驗證每個角色是否包含必要字段
            validated_characters = []
            for char in characters:
                if isinstance(char, dict) and "id" in char and "name" in char:
                    validated_characters.append(char)
                else:
                    logger.warning(f"跳過格式不正確的角色數據: {char}")
            
            if not validated_characters:
                logger.warning("沒有有效的角色數據，使用默認角色")
                return [{"id": "1", "name": "默認病患"}]
            
            return validated_characters
        except Exception as e:
            logger.error(f"獲取角色列表失敗: {e}")
            # 返回默認角色
            return [{"id": "1", "name": "默認病患"}]
    
    def send_text_message(self, text: str, response_format: str = "text") -> Dict[str, Any]:
        """發送文本消息並獲取回應
        
        Args:
            text: 用戶輸入的文本
            response_format: 回應格式 ("text" 或 "audio")
            
        Returns:
            API 回應
        """
        try:
            url = f"{self.base_url}/api/dialogue/text"
            data = {
                "text": text,
                "character_id": self.character_id or "1",  # 確保始終有角色ID
                "session_id": self.session_id,
                "response_format": response_format
            }
            
            logger.info(f"發送文本消息到 {url}: {data}")
            response = requests.post(url, json=data)
            
            # 檢查是否為音頻回應
            if response_format == "audio" and response.headers.get('Content-Type') == 'audio/wav':
                # 從頭部獲取會話ID
                self.session_id = response.headers.get('X-Session-ID')
                logger.info(f"收到音頻回應，會話ID: {self.session_id}")
                
                # 保存音頻
                audio_file = self._save_audio_response(response, text)
                logger.info(f"音頻已保存到: {audio_file}")
                
                return {
                    "status": "success",
                    "audio_file": audio_file,
                    "session_id": self.session_id,
                    "is_audio": True
                }
            else:
                # 解析 JSON 回應
                try:
                    data = response.json()
                    logger.info(f"收到JSON回應: {data}")
                    # 更新會話ID
                    if "session_id" in data:
                        self.session_id = data["session_id"]
                    return data
                except json.JSONDecodeError:
                    logger.error(f"無法解析JSON回應: {response.text}")
                    return {
                        "status": "error",
                        "message": "無法解析回應",
                        "responses": ["服務器回應格式錯誤"]
                    }
        except Exception as e:
            logger.error(f"發送文本消息失敗: {e}")
            return {
                "status": "error", 
                "message": str(e),
                "responses": ["無法連接到服務器"]
            }
    
    def send_audio_message(self, audio_file_path: str, response_format: str = "text") -> Dict[str, Any]:
        """發送音頻消息並獲取回應
        
        Args:
            audio_file_path: 音頻文件路徑
            response_format: 回應格式 ("text" 或 "audio")
            
        Returns:
            API 回應
        """
        try:
            url = f"{self.base_url}/api/dialogue/audio"
            logger.info(f"發送音頻消息到 {url}, 文件: {audio_file_path}")
            
            with open(audio_file_path, "rb") as audio_file:
                files = {"audio_file": audio_file}
                data = {
                    "character_id": self.character_id or "1",  # 確保始終有角色ID
                    "response_format": response_format
                }
                
                if self.session_id:
                    data["session_id"] = self.session_id
                    
                response = requests.post(url, files=files, data=data)
                
                # 檢查是否為音頻回應
                if response_format == "audio" and response.headers.get('Content-Type') == 'audio/wav':
                    # 從頭部獲取會話ID
                    self.session_id = response.headers.get('X-Session-ID')
                    logger.info(f"收到音頻回應，會話ID: {self.session_id}")
                    
                    # 保存音頻
                    audio_file = self._save_audio_response(response, audio_file_path)
                    logger.info(f"音頻已保存到: {audio_file}")
                    
                    return {
                        "status": "success",
                        "audio_file": audio_file,
                        "session_id": self.session_id,
                        "is_audio": True
                    }
                else:
                    # 解析 JSON 回應
                    try:
                        data = response.json()
                        logger.info(f"收到JSON回應: {data}")
                        # 更新會話ID
                        if "session_id" in data:
                            self.session_id = data["session_id"]
                        return data
                    except json.JSONDecodeError:
                        logger.error(f"無法解析JSON回應: {response.text}")
                        return {
                            "status": "error",
                            "message": "無法解析回應",
                            "responses": ["服務器回應格式錯誤"]
                        }
        except Exception as e:
            logger.error(f"發送音頻消息失敗: {e}")
            return {
                "status": "error", 
                "message": str(e),
                "responses": ["無法連接到服務器"]
            }
    
    def _save_audio_response(self, response, source) -> str:
        """保存音頻回應到臨時文件
        
        Args:
            response: API 回應
            source: 原始請求內容 (用於生成唯一文件名)
            
        Returns:
            保存的音頻文件路徑
        """
        # 創建臨時文件
        audio_filename = f"response_{hash(str(source))}.wav"
        temp_dir = tempfile.gettempdir()
        audio_path = os.path.join(temp_dir, audio_filename)
        
        # 保存音頻內容
        with open(audio_path, "wb") as f:
            f.write(response.content)
        
        return audio_path
    
    def set_character(self, character_id: str) -> None:
        """設置當前角色ID
        
        Args:
            character_id: 角色ID
        """
        if not character_id:
            logger.warning("嘗試設置空角色ID，使用默認值")
            character_id = "1"
            
        logger.info(f"設置角色ID: {character_id}")
        self.character_id = character_id
        # 切換角色時重置會話ID
        self.session_id = None
    
    def reset_session(self) -> None:
        """重置當前會話"""
        logger.info("重置會話")
        self.session_id = None 