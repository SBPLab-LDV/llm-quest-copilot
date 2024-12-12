import google.generativeai as genai
from ..utils.config import load_config

class GeminiClient:
    def __init__(self):
        config = load_config()
        genai.configure(api_key=config['google_api_key'])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def generate_response(self, prompt: str) -> str:
        """生成回應並確保格式正確"""
        try:
            # 設定生成參數以確保更好的格式控制
            generation_config = {
                "temperature": 0.9,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
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
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # 直接返回模型的回應，不做額外處理
            return response.text.strip()
            
        except Exception as e:
            # 如果生成失敗，返回一個基本的錯誤回應
            return '{"responses": ["抱歉，我現在無法正確回應"],"state": "CONFUSED"}'