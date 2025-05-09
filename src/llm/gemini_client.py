import google.generativeai as genai
from ..utils.config import load_config
import logging
import os
import base64
import json

class GeminiClient:
    def __init__(self):
        config = load_config()
        genai.configure(api_key=config['google_api_key'])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # Create a multimodal model instance for audio processing
        self.multimodal_model = genai.GenerativeModel('gemini-2.0-flash-exp')
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
        """將音頻文件轉換為文本，同時處理斷斷續續的語音並提供多個可能的完整句子選項
        
        Args:
            audio_file_path: 音頻文件路徑 (WAV格式)
            
        Returns:
            識別結果的 JSON 字符串，包含原始轉錄和多個可能完整句子選項
        """
        try:
            self.logger.info(f"===== 開始音頻轉文本 =====")
            self.logger.info(f"音頻文件: {audio_file_path}")
            
            # 檢查文件是否存在
            if not os.path.exists(audio_file_path):
                self.logger.error(f"音頻文件不存在: {audio_file_path}")
                return json.dumps({
                    "original": "無法處理音頻文件：文件不存在",
                    "options": ["無法處理音頻文件：文件不存在"]
                })
            
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
                return json.dumps({
                    "original": "無法讀取音頻文件",
                    "options": ["無法讀取音頻文件"]
                })
            
            # 構建專門處理病患斷斷續續語音的提示詞
            prompt = """
            請仔細聆聽這段錄音。這是一位病患的語音，可能因為疾病或身體狀況而斷斷續續，無法流暢表達。

            請執行以下步驟：
            1. 首先，忠實記錄病患實際說的內容，包括停頓、重複和不完整的部分，使用省略號(...)表示停頓
            2. 然後，基於聽到的內容，推測病患可能想表達的完整句子，提供 3-5 個不同的合理可能性
            3. 確保所有推測都符合醫療情境下的病患可能表達的內容

            將結果格式化為 JSON 格式，包含以下字段：
            - original: 原始識別的內容，包括停頓和不完整部分
            - options: 3-5 個推測的完整句子選項數組

            如果完全聽不清或無法識別，請回覆包含「無法識別錄音內容」的 JSON。
            如果是背景噪音或沒有語音，請回覆包含「錄音中沒有清晰的語音」的 JSON。

            請直接返回正確的 JSON 格式，不要包含任何額外解釋、markdown 標記或代碼塊標記。
            例如：
            {"original": "我...頭痛...", "options": ["我感到頭痛", "我有頭痛症狀", "我的頭很痛"]}
            """
            
            # 按照 genai 庫要求的格式準備多模態內容
            content = {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": base64.b64encode(audio_data).decode('utf-8')
                        }
                    }
                ]
            }
            
            # 設定生成參數
            generation_config = {
                "temperature": 0.4,  # 稍微提高溫度以允許多樣化的推測
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
            result_text = response.text.strip()
            self.logger.info(f"===== 音頻識別完成 =====")
            self.logger.debug(f"識別結果: '{result_text[:100]}...'")
            
            # 清理結果文本中可能包含的markdown代碼塊標記
            # 移除可能的代碼塊標記 ```json 和 ```
            cleaned_text = result_text
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # 驗證 JSON 格式
            try:
                # 嘗試解析回應為 JSON
                json_result = json.loads(cleaned_text)
                
                # 確保有必要的字段
                if "original" not in json_result or "options" not in json_result:
                    self.logger.warning(f"回應缺少必要字段: {json_result}")
                    # 構造格式正確的回應
                    if "original" in json_result and isinstance(json_result["original"], str):
                        original = json_result["original"]
                    else:
                        original = result_text
                    
                    return json.dumps({
                        "original": original,
                        "options": [original]
                    })
                
                # 格式正確，返回格式化的 JSON 字符串
                return json.dumps(json_result)
            except json.JSONDecodeError:
                # 不是 JSON 格式，將其轉換為正確的格式
                self.logger.warning(f"回應不是 JSON 格式: {result_text}")
                return json.dumps({
                    "original": result_text,
                    "options": [result_text]
                })
            
        except Exception as e:
            self.logger.error(f"音頻識別失敗: {e}", exc_info=True)
            # 返回格式正確的錯誤 JSON
            return json.dumps({
                "original": "音頻識別過程中發生錯誤",
                "options": ["音頻識別過程中發生錯誤，請重試"]
            })