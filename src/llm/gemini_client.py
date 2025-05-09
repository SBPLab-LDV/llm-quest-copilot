import google.generativeai as genai
from ..utils.config import load_config
import logging
import os
import base64

class GeminiClient:
    def __init__(self):
        config = load_config()
        genai.configure(api_key=config['google_api_key'])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # Create a multimodal model instance for audio processing
        self.multimodal_model = genai.GenerativeModel('gemini-2.0-pro-vision-exp')
        self.logger = logging.getLogger(__name__)
        
    def generate_response(self, prompt: str) -> str:
        """生成回應並確保格式正確"""
        try:
            # 詳細記錄發送給 API 的請求
            self.logger.info(f"===== 發送請求到 Gemini API =====")
            self.logger.info(f"模型: gemini-2.0-flash-exp")
            self.logger.debug(f"提示詞: {prompt[:100]}... (截斷顯示)")
            
            # 設定生成參數以確保更好的格式控制
            generation_config = {
                "temperature": 0.9,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            self.logger.debug(f"生成參數: {generation_config}")
            
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
            ]
            
            # 呼叫 API
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # 記錄 API 回傳的結果
            self.logger.info(f"===== 接收到 Gemini API 回應 =====")
            self.logger.debug(f"回應長度: {len(response.text)}")
            
            # 紀錄最初和最後的一部分回應
            response_text = response.text.strip()
            self.logger.debug(f"回應前100字符: {response_text[:100]}...")
            if len(response_text) > 200:
                self.logger.debug(f"回應最後100字符: ...{response_text[-100:]}")
            
            # 直接返回模型的回應，不做額外處理
            return response_text
            
        except Exception as e:
            # 記錄錯誤
            self.logger.error(f"Gemini API 呼叫失敗: {e}", exc_info=True)
            # 如果生成失敗，返回一個基本的錯誤回應
            return '{"responses": ["抱歉，我現在無法正確回應"],"state": "CONFUSED"}'
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """將音頻文件轉換為文本
        
        Args:
            audio_file_path: 音頻文件路徑 (WAV格式)
            
        Returns:
            識別出的文本
        """
        try:
            self.logger.info(f"===== 開始音頻轉文本 =====")
            self.logger.info(f"音頻文件: {audio_file_path}")
            
            # 檢查文件是否存在
            if not os.path.exists(audio_file_path):
                self.logger.error(f"音頻文件不存在: {audio_file_path}")
                return "無法處理音頻文件：文件不存在"
            
            # 讀取音頻文件
            try:
                with open(audio_file_path, "rb") as f:
                    audio_data = f.read()
                
                file_size = len(audio_data) / 1024  # KB
                self.logger.debug(f"音頻文件大小: {file_size:.2f} KB")
                
                # 檢查文件大小，Gemini API 可能有限制
                if file_size > 10 * 1024:  # 10 MB
                    self.logger.warning(f"音頻文件過大 ({file_size:.2f} KB)，可能超過 API 限制")
            except Exception as e:
                self.logger.error(f"讀取音頻文件失敗: {e}", exc_info=True)
                return "無法讀取音頻文件"
            
            # 構建提示詞，包括任務描述和音頻數據
            prompt = """
            請識別這段錄音中的語音內容，輸出識別的文本。這是一段病患與醫護人員之間的對話錄音。
            請只返回識別出的文本，不要包含任何額外解釋或格式。
            如果聽不清或無法識別，請回覆「無法識別錄音內容」。
            如果是背景噪音或沒有語音，請回覆「錄音中沒有清晰的語音」。
            """
            
            # 準備多模態內容（文本+音頻）
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "blob", 
                    "mime_type": "audio/wav",
                    "data": audio_data
                }
            ]
            
            # 設定生成參數
            generation_config = {
                "temperature": 0.2,  # 保持低溫度以獲得更準確的轉錄
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 1024,
            }
            
            self.logger.info(f"調用 Gemini 多模態 API 進行音頻識別")
            
            # 調用 API
            response = self.multimodal_model.generate_content(
                content,
                generation_config=generation_config
            )
            
            # 處理回應
            transcription = response.text.strip()
            self.logger.info(f"===== 音頻識別完成 =====")
            self.logger.debug(f"識別結果: '{transcription[:100]}...'")
            
            return transcription
            
        except Exception as e:
            self.logger.error(f"音頻識別失敗: {e}", exc_info=True)
            return "音頻識別過程中發生錯誤，請重試"