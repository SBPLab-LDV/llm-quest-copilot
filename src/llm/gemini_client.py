import google.generativeai as genai
from ..utils.config import load_config
import logging

class GeminiClient:
    def __init__(self):
        config = load_config()
        genai.configure(api_key=config['google_api_key'])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
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