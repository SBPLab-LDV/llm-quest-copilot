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
    
    def send_text(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """發送文本消息並獲取回應
        
        Args:
            request_data: 請求數據，包含文本和其他可選參數
            
        Returns:
            API 回應
        """
        try:
            url = f"{self.base_url}/api/dialogue/text"
            
            # 確保必要的字段
            if "text" not in request_data:
                logger.error("請求缺少必要字段: text")
                return {
                    "status": "error",
                    "message": "請求缺少必要字段: text",
                    "responses": ["請提供文本輸入"]
                }
                
            # 準備最終的請求數據
            final_request = request_data.copy()
            
            # 重要修改：確保即使提供 character_config 也要提供 character_id
            # 根據API錯誤，character_id 是必要參數
            if "character_id" not in final_request or not final_request["character_id"]:
                final_request["character_id"] = self.character_id or "1"
                logger.info(f"添加必要的character_id參數: {final_request['character_id']}")
            
            # 處理角色配置
            if "character_config" in request_data and request_data["character_config"]:
                # 確保character_config是JSON格式化的字符串
                if isinstance(request_data["character_config"], dict):
                    logger.info(f"序列化自定義角色配置為JSON")
                    final_request["character_config"] = json.dumps(request_data["character_config"])
                logger.info(f"使用提供的自定義角色配置: {final_request['character_config']}")
            elif self.character_config:
                # 使用客戶端存儲的自定義配置
                logger.info(f"使用客戶端存儲的自定義角色配置")
                final_request["character_config"] = json.dumps(self.character_config)
            
            # 使用當前會話ID（如果未提供）
            if "session_id" not in final_request or not final_request["session_id"]:
                final_request["session_id"] = self.session_id
            
            # 使用默認回應格式（如果未提供）
            if "response_format" not in final_request:
                final_request["response_format"] = "text"
            
            # 發送請求
            logger.info(f"發送文本消息到 {url}: {final_request}")
            response = requests.post(url, json=final_request)
            
            # 添加更多詳細的錯誤處理和日誌記錄
            if response.status_code != 200:
                logger.error(f"API 請求失敗! 狀態碼: {response.status_code}")
                logger.error(f"錯誤詳情: {response.text}")
                
                # 嘗試從錯誤響應中提取更多信息
                error_message = "無法連接到服務器"
                try:
                    error_data = response.json()
                    if "detail" in error_data:
                        error_message = error_data["detail"]
                except Exception:
                    # 如果無法解析 JSON，嘗試使用文本內容
                    error_message = response.text if response.text else error_message
                
                return {
                    "status": "error",
                    "message": f"API 錯誤 ({response.status_code}): {error_message}",
                    "responses": [f"無法處理您的請求: {error_message}"]
                }
                
            # 檢查是否為音頻回應
            if final_request.get("response_format") == "audio" and response.headers.get('Content-Type') == 'audio/wav':
                # 從頭部獲取會話ID
                self.session_id = response.headers.get('X-Session-ID')
                logger.info(f"收到音頻回應，會話ID: {self.session_id}")
                
                # 保存音頻
                audio_file = self._save_audio_response(response, final_request["text"])
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
    
    def send_audio(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """發送音頻消息並獲取回應
        
        Args:
            request_data: 請求數據字典，必須包含 audio_file 字段
            
        Returns:
            API 回應
        """
        try:
            # 檢查必要字段
            if "audio_file" not in request_data or not request_data["audio_file"]:
                logger.error("音頻請求缺少必要字段: audio_file")
                return {
                    "status": "error",
                    "message": "音頻請求缺少必要字段: audio_file",
                    "responses": ["請提供音頻文件"]
                }
            
            audio_file_path = request_data["audio_file"]
            url = f"{self.base_url}/api/dialogue/audio"
            logger.info(f"發送音頻消息到 {url}, 文件: {audio_file_path}")
            
            with open(audio_file_path, "rb") as audio_file:
                files = {"audio_file": audio_file}
                data = {}
                
                # 複製請求參數到 data（排除 audio_file）
                for key, value in request_data.items():
                    if key != "audio_file":
                        # 如果是字典型別（如角色配置），序列化為JSON
                        if key == "character_config" and isinstance(value, dict):
                            # 直接將JSON字符串作為單獨參數傳遞，而不是作為form-data
                            data["character_config"] = json.dumps(value)
                            logger.info(f"將character_config序列化為JSON: {data['character_config']}")
                        else:
                            data[key] = value
                
                # 確保即使提供 character_config 也要提供 character_id
                # 根據API錯誤，character_id 是必要參數
                if "character_id" not in data or not data["character_id"]:
                    data["character_id"] = self.character_id or "1"
                    logger.info(f"添加必要的character_id參數: {data['character_id']}")
                
                # 如果沒有提供角色配置，使用客戶端默認值
                if "character_config" not in data and self.character_config:
                    data["character_config"] = json.dumps(self.character_config)
                    logger.info(f"使用客戶端默認角色配置: {data['character_config']}")
                
                # 如果沒有提供會話ID，使用客戶端默認值
                if "session_id" not in data and self.session_id:
                    data["session_id"] = self.session_id
                
                # 如果沒有提供回應格式，使用默認文本格式
                if "response_format" not in data:
                    data["response_format"] = "text"
                    
                logger.info(f"完整的請求數據: {data}")
                response = requests.post(url, files=files, data=data)
                
                # 檢查是否為音頻回應
                if data.get("response_format") == "audio" and response.headers.get('Content-Type') == 'audio/wav':
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
                            
                        # 確保 speech_recognition_options 存在並且是有效的列表
                        if "speech_recognition_options" in data:
                            if not isinstance(data["speech_recognition_options"], list):
                                logger.warning(f"speech_recognition_options 不是列表類型，轉換為列表")
                                # 如果不是列表，嘗試轉換為列表
                                if data["speech_recognition_options"]:
                                    data["speech_recognition_options"] = [str(data["speech_recognition_options"])]
                                else:
                                    data["speech_recognition_options"] = []
                            # 確保所有選項都是字符串
                            data["speech_recognition_options"] = [str(opt) for opt in data["speech_recognition_options"] if opt]
                            
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
            
        # 記錄之前的角色設置
        previous_char_id = self.character_id
        previous_config = self.character_config
        
        # 更新角色ID
        logger.info(f"設置角色ID: {character_id}")
        self.character_id = character_id
        
        # 更新角色配置
        if character_config:
            logger.info(f"設置自定義角色配置:")
            
            # 記錄關鍵部分以便調試
            if isinstance(character_config, dict):
                logger.info(f"  名稱: {character_config.get('name', '未指定')}")
                logger.info(f"  個性: {character_config.get('persona', '未指定')}")
                logger.info(f"  背景: {character_config.get('backstory', '未指定')[:50]}...")
                
                # 檢查詳細設定格式
                details = character_config.get('details', {})
                if details:
                    logger.info(f"  固定設定: {details.get('fixed_settings', {})}")
                    logger.info(f"  浮動設定: {details.get('floating_settings', {})}")
            
            self.character_config = character_config
        else:
            logger.info("未設置自定義角色配置，使用默認角色ID")
            self.character_config = None
            
        logger.info(f"角色設置已從 [{previous_char_id}, 配置={previous_config != None}] 變更為 [{self.character_id}, 配置={self.character_config != None}]")
    
    def update_selected_response(self, session_id: str, selected_response: str) -> Dict[str, Any]:
        """更新已選擇的回應到伺服器，並將回應加入對話歷史
        
        Args:
            session_id: 會話ID
            selected_response: 患者選擇的回應
            
        Returns:
            服務器回應字典或錯誤字典
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
                    return {"status": "error", "message": "会话ID为空", "responses": ["无法处理您的选择"]}
            
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
                    # 解析服務器返回的回應
                    response_data = response.json()
                    logger.info(f"服務器返回的回應: {response_data}")
                    
                    # 如果服務器返回新的會話ID，更新客戶端的會話ID
                    if "session_id" in response_data and response_data["session_id"]:
                        if response_data["session_id"] != self.session_id:
                            logger.info(f"服务器返回新的会话ID: {response_data['session_id']}")
                            self.session_id = response_data["session_id"]
                    
                    # 返回服務器的完整回應
                    return response_data
                except ValueError as e:
                    logger.error(f"解析服務器回應時出錯: {e}")
                    return {
                        "status": "error", 
                        "message": "無法解析服務器回應", 
                        "responses": ["選擇已記錄，但無法獲取下一步回應"]
                    }
            else:
                logger.warning(f"發送回應選擇失敗: {response.status_code} {response.text}")
                return {
                    "status": "error", 
                    "message": f"發送選擇失敗: {response.status_code}", 
                    "responses": ["無法處理您的選擇，請稍後再試"]
                }
        except Exception as e:
            logger.error(f"更新選擇的回應失敗: {e}", exc_info=True)
            return {
                "status": "error", 
                "message": str(e), 
                "responses": ["發生錯誤，無法處理您的選擇"]
            }
    
    def reset_session(self) -> None:
        """重置當前會話"""
        logger.info("重置會話")
        self.session_id = None 