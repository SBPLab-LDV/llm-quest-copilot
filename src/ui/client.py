import requests
import json
import os
import tempfile
import sys
import codecs
from typing import Dict, Optional, List, Any, Tuple
import logging

# 直接使用應用程序中已配置的 SafeStreamHandler
# 不再嘗試修改控制台編碼
# 僅配置客戶端模塊日誌記錄
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
        self.character_config = None
    
    def get_characters(self) -> List[Dict[str, Any]]:
        """獲取可用角色列表
        
        Returns:
            角色列表
        """
        try:
            # 注意：本地測試環境可能沒有角色列表 API
            # 返回一些預設角色以便測試
            logger.info(f"返回預設角色列表進行測試")
            return [
                {"id": "1", "name": "測試病患1"},
                {"id": "2", "name": "測試病患2"},
                {"id": "custom", "name": "自定義病患"}
            ]
            
            # 保留原始代碼但暫時不使用
            '''
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
            '''
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
            
            # 添加角色配置（如果有）
            if self.character_config:
                data["character_config"] = self.character_config
            
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
                
                # 添加角色配置（如果有）
                if self.character_config:
                    # 由於 multipart/form-data 格式限制，需要將字典序列化為 JSON 字符串
                    data["character_config_json"] = json.dumps(self.character_config)
                    
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
    
    def set_character(self, character_id: str, character_config: Optional[Dict[str, Any]] = None) -> None:
        """設置當前角色ID和配置
        
        Args:
            character_id: 角色ID
            character_config: 角色配置
        """
        if not character_id:
            logger.warning("嘗試設置空角色ID，使用默認值")
            character_id = "1"
            
        logger.info(f"設置角色ID: {character_id}")
        self.character_id = character_id
        
        if character_config:
            logger.info(f"設置角色配置: {character_config}")
            self.character_config = character_config
        else:
            self.character_config = None
            
        # 不再自动重置会话ID，这是导致问题的原因
        # self.session_id = None
    
    def update_selected_response(self, session_id: str, selected_response: str) -> bool:
        """更新已選擇的回應到伺服器，並將回應加入對話歷史
        
        Args:
            session_id: 會話ID
            selected_response: 患者選擇的回應
            
        Returns:
            是否成功發送
        """
        logger.info(f"更新選擇的回應: '{selected_response}'")
        
        try:
            if not session_id:
                logger.error("无法发送选择的回应: 会话ID为空")
                # 如果没有提供会话ID但客户端有会话ID，尝试使用客户端会话ID
                if self.session_id:
                    logger.info(f"尝试使用客户端会话ID: {self.session_id}")
                    session_id = self.session_id
                else:
                    return False
            
            # 确保本地会话ID与传入的会话ID一致
            if self.session_id != session_id:
                logger.warning(f"会话ID不匹配，更新客户端会话ID: 从 {self.session_id} 到 {session_id}")
                self.session_id = session_id
            
            logger.info(f"為會話 {session_id} 發送選擇的回應: '{selected_response}'")
            
            # 發送選擇的回應到伺服器
            url = f"{self.base_url}/api/dialogue/select_response"
            response = requests.post(url, json={
                "session_id": session_id,
                "selected_response": selected_response
            })
            
            # 檢查回應
            if response.status_code == 200:
                logger.info("回應選擇已成功發送到伺服器")
                try:
                    # 尝试解析返回的JSON数据，查看是否有更新的会话ID
                    response_data = response.json()
                    if "session_id" in response_data and response_data["session_id"]:
                        if response_data["session_id"] != self.session_id:
                            logger.info(f"服务器返回新的会话ID: {response_data['session_id']}")
                            self.session_id = response_data["session_id"]
                    return True
                except ValueError:
                    logger.debug("服务器未返回JSON数据或无需更新会话ID")
                    return True
            else:
                logger.warning(f"發送回應選擇失敗: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"更新選擇的回應失敗: {e}", exc_info=True)
            return False
    
    def reset_session(self) -> None:
        """重置當前會話"""
        logger.info("重置會話")
        self.session_id = None 