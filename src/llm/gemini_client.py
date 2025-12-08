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
    
    def transcribe_audio(self, audio_file_path: str, mime_type: str = None, mode: str = "patient") -> str:
        """將音頻文件轉換為文本
        
        Args:
            audio_file_path: 音頻文件路徑
            mime_type: 音頻文件的 MIME 類型
            mode: 轉錄模式，"patient" (病患模式，會推測選項) 或 "general" (一般模式，忠實轉錄)
            
        Returns:
            識別結果的 JSON 字符串
        """
        try:
            # 如果未提供 MIME 類型，嘗試自動檢測
            if mime_type is None:
                from ..utils.audio_processor import get_audio_mime_type
                mime_type = get_audio_mime_type(audio_file_path)
                if mime_type is None:
                    # 默認使用 audio/wav
                    file_ext = os.path.splitext(audio_file_path)[1].lower()
                    self.logger.warning(f"無法檢測音頻格式 {file_ext}，使用默認 MIME 類型 audio/wav")
                    mime_type = "audio/wav"
                else:
                    self.logger.info(f"自動檢測到音頻格式: {mime_type}")
            
            self.logger.info(f"===== 開始音頻轉文本 (模式: {mode}) =====")
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
            
            if mode == "general":
                # 一般模式：忠實轉錄
                prompt = """
                請將這段錄音內容忠實轉錄為文字。
                
                **要求：**
                1. 逐字轉錄，不要遺漏。
                2. 不要添加任何解釋、標點符號以外的符號。
                3. 如果語音清晰，直接輸出內容。
                4. 如果語音包含多個句子，請用標點符號分隔。
                
                **輸出格式要求：**
                請返回標準JSON格式，包含：
                - "original": 轉錄的文字內容
                - "options": [轉錄的文字內容] (為了保持格式一致，請將內容放入陣列)
                
                請直接返回JSON格式，不要包含任何markdown標記。
                如果完全無法識別，請返回：{"original": "無法識別", "options": []}
                """
            else:
                # 病患模式：推測意圖 (原有的 Prompt)
                prompt = """
                請仔細聆聽這段錄音。這是一位口腔癌住院病患的語音，請根據以下醫療情境和病患特殊狀況進行分析：

                **病患醫療背景：**
                - 口腔癌患者，可能接受過手術、化療或放射治療
                - 可能有口腔潰瘍、黏膜炎、張口困難等副作用
                - 發音器官（舌頭、牙齒、嘴唇、軟顎）可能受損
                - 可能裝有鼻胃管、氣切管或其他維生設備
                - 正在住院治療中，處於醫療監護環境

                **語音表達特點：**
                - 咬字不清、發音模糊（特別是需要舌頭或嘴唇配合的音）
                - 可能有漏風音、鼻音過重或氣音
                - 說話速度較慢，經常停頓休息
                - 可能因疼痛而中斷說話
                - 音量較小或時強時弱

                **住院情境下具體需求推測指南：**
                當聽到關鍵詞時，請推測具體的完整句子：

                1. **疼痛相關：**
                   - "痛" → "我嘴巴很痛，需要止痛藥" / "我頭很痛，可以幫我調整枕頭嗎" / "我傷口很痛，請護士來看一下"
                   - "不舒服" → "我覺得噁心想吐" / "我胸口悶悶的不舒服" / "我躺著不舒服，想要坐起來"

                2. **飲食相關：**
                   - "餓" / "吃" → "我餓了，什麼時候可以吃流質食物" / "我想吃點冰淇淋舒緩口腔" / "我可以吃軟質食物嗎"
                   - "水" / "喝" → "我想喝溫開水潤喉" / "我嘴巴很乾，可以用濕棉棒嗎" / "我想喝點果汁"

                3. **生理需求：**
                   - "尿" / "廁所" → "我需要小便，請幫我拿尿壺" / "我想上大號，需要人扶我去廁所" / "我尿急，請快點幫忙"
                   - "洗" → "我想刷牙清潔口腔" / "我想洗臉擦身體" / "我想漱口去除異味"

                4. **醫療照護：**
                   - "護士" / "醫生" → "請叫護士來幫我換藥" / "我想問醫生什麼時候可以出院" / "護士，我的點滴好像有問題"
                   - "藥" → "我需要吃止痛藥了" / "我忘記吃血壓藥了" / "這個藥讓我想吐"

                5. **情緒支持：**
                   - "怕" → "我很怕開刀會不會有後遺症" / "我擔心家裡的小孩沒人照顧" / "我害怕治療效果不好"
                   - "家人" → "我想打電話給我老婆" / "我的小孩什麼時候來看我" / "請幫我聯絡我兒子"

                6. **環境調節：**
                   - "冷" / "熱" → "我覺得很冷，可以再蓋一條被子嗎" / "冷氣太強了，請調高一點溫度"
                   - "吵" → "隔壁病床太吵了，我睡不著" / "外面施工聲音太大，可以關窗戶嗎"

                **重要原則：**
                1. 避免產生模糊不清的句子（如僅"我想吃"、"我要"、"幫我"）
                2. 必須包含具體的行動、物品或情境描述
                3. 考慮口腔癌病患的實際限制和需求
                4. 結合住院環境的實際情況
                5. 優先考慮醫療相關的具體需求

                **輸出格式要求：**
                請返回標準JSON格式，包含：
                - "original": 原始錄音內容的忠實記錄
                - "options": 4個具體完整的句子，每個都包含明確的情境和需求

                **正確範例：**
                {"original": "我...想...吃[含糊]...", "options": ["我想吃點冰淇淋舒緩口腔疼痛", "我想吃流質食物，肚子餓了", "我想吃點軟質的粥或湯", "我想吃藥，忘記吃止痛藥了"]}

                **錯誤範例（避免）：**
                {"original": "我...想...吃[含糊]...", "options": ["我想吃", "我要吃東西", "給我食物"]}

                請直接返回JSON格式，不要包含任何markdown標記或額外解釋。
                如果完全無法識別，請返回：{"original": "無法識別", "options": ["建議重新錄音或請護理人員協助確認需求"]}
                """
            
            # 按照 genai 庫要求的格式準備多模態內容
            content = {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,  # 使用動態 MIME 類型
                            "data": base64.b64encode(audio_data).decode('utf-8')
                        }
                    }
                ]
            }
            
            self.logger.info(f"使用 MIME 類型: {mime_type}")
            
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