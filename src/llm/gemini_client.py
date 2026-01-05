import google.generativeai as genai
from ..utils.config import load_config
import logging
import os
import base64
import json
import hashlib

from ..core.audio.context_utils import (
    format_history_for_audio,
    build_available_audio_contexts,
    summarize_character,
    build_audio_template_rules,
)
from ..core.dspy.audio_modules import get_audio_prompt_composer
from typing import Optional

class GeminiClient:
    def __init__(self):
        config = load_config()
        genai.configure(api_key=config['google_api_key'])
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        # Create a multimodal model instance for audio processing
        self.multimodal_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.logger = logging.getLogger(__name__)
        self.logging_cfg = config.get('logging', {}) or {}
        self.audio_cfg = config.get('audio', {}) or {}
        self._prompt_manager = None
        self._last_audio_prompt: Optional[str] = None
        self._last_audio_system_prompt: Optional[str] = None
        self._last_audio_user_prompt: Optional[str] = None
        self._last_audio_template_rules: Optional[str] = None
        self._last_audio_raw: Optional[str] = None
        self._last_audio_clean: Optional[str] = None
        self._last_trace_id: Optional[str] = None
        # Diagnostics
        self._last_audio_used_dspy: bool = False
        self._last_audio_signature: Optional[str] = None
        # Self-annotation fields
        self._last_audio_raw_transcript: Optional[str] = None
        self._last_audio_keyword_completion: Optional[list] = None
        
    def _infer_mime_type(self, path: str) -> str:
        try:
            ext = os.path.splitext(path)[1].lower()
        except Exception:
            ext = ''
        return {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
        }.get(ext, 'audio/wav')

    def generate_response(self, prompt: str) -> str:
        """生成回應並確保格式正確"""
        try:
            # 詳細記錄發送給 API 的請求
            self.logger.info(f"===== 發送請求到 Gemini API =====")
            self.logger.info(f"模型: gemini-2.0-flash-exp")
            # 安全地處理 prompt 日誌
            if isinstance(prompt, str):
                self.logger.debug(f"提示詞: {prompt[:100]}... (截斷顯示)")
            else:
                self.logger.debug(f"提示詞類型: {type(prompt)}, 內容: {str(prompt)[:100]}... (截斷顯示)")
            
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
            self.logger.error(f"Gemini API 呼叫失敗: {e}", exc_info=True)
            error_payload = {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
            return json.dumps(error_payload, ensure_ascii=False)
    
    def transcribe_audio(self, audio_file_path: str,
                         character: object = None,
                         conversation_history: object = None,
                         session_id: str = None,
                         trace_id: str = None) -> str:
        """將音頻文件轉換為文本，回傳標準 JSON 字串。"""
        try:
            self.logger.info("===== 開始音頻轉文本 =====")
            self.logger.info(f"音頻文件: {audio_file_path}")

            if not os.path.exists(audio_file_path):
                self.logger.error(f"音頻文件不存在: {audio_file_path}")
                return json.dumps({
                    "original": "無法處理音頻文件：文件不存在",
                    "options": ["無法處理音頻文件：文件不存在"]
                })

            try:
                with open(audio_file_path, "rb") as f:
                    audio_data = f.read()
                file_size = len(audio_data) / 1024
                self.logger.debug(f"音頻文件大小: {file_size:.2f} KB")
                try:
                    sha = hashlib.sha256(audio_data).hexdigest()[:8]
                    self.logger.info(
                        f"Audio meta: size_kb={file_size:.2f}, sha256_8={sha}, session_id={session_id or ''}, trace_id={trace_id or ''}"
                    )
                except Exception:
                    pass
                if file_size > 10 * 1024:
                    self.logger.warning(f"音頻文件過大 ({file_size:.2f} KB)，可能超過 API 限制")
            except Exception as e:
                self.logger.error(f"讀取音頻文件失敗: {e}", exc_info=True)
                return json.dumps({
                    "original": "無法讀取音頻文件",
                    "options": ["無法讀取音頻文件"]
                })

            option_count = int(self.audio_cfg.get('option_count', 4) or 4)
            prompt_via_dspy = bool(self.audio_cfg.get('prompt_via_dspy', False))
            use_context = bool(self.audio_cfg.get('use_context', False))

            # Diagnostics: log audio configuration
            self.logger.info(
                "[AudioCfg] prompt_via_dspy=%s, use_context=%s, option_count=%s",
                prompt_via_dspy, use_context, option_count,
            )

            character_profile = summarize_character(character) if character else ""
            history_text = ""
            if use_context and conversation_history is not None:
                try:
                    history_text = format_history_for_audio(
                        conversation_history,
                        getattr(character, 'name', None) if character else None,
                        getattr(character, 'persona', None) if character else None,
                    )
                except Exception:
                    history_text = ""
            available_contexts = build_available_audio_contexts() if use_context else ""
            template_rules = build_audio_template_rules(option_count)

            self._last_trace_id = trace_id
            self._last_audio_template_rules = template_rules

            if prompt_via_dspy:
                composer = get_audio_prompt_composer()
                # Diagnostics: record and log signature/inputs presence
                sig_name = None
                try:
                    sig_name = getattr(composer, 'signature').__name__  # type: ignore[attr-defined]
                except Exception:
                    sig_name = str(getattr(composer, 'signature', 'unknown'))
                self._last_audio_used_dspy = True
                self._last_audio_signature = sig_name
                self.logger.info(
                    "[DSPy] Using AudioPromptComposerModule (Signature=%s) | profile_len=%s, history_len=%s, contexts_len=%s, rules_len=%s",
                    sig_name,
                    len(character_profile or ""),
                    len(history_text or ""),
                    len(available_contexts or ""),
                    len(template_rules or ""),
                )
                prediction = composer(
                    character_profile=character_profile,
                    conversation_history=history_text,
                    available_contexts=available_contexts,
                    template_rules=template_rules,
                    option_count=option_count,
                )
                system_prompt = getattr(prediction, 'system_prompt', '')
                user_prompt = getattr(prediction, 'user_prompt', '')
                self.logger.info(
                    "[DSPy] Composer output lengths | system=%s chars, user=%s chars",
                    len(system_prompt or ""), len(user_prompt or "")
                )
                combined_prompt = "\n\n".join([p for p in [system_prompt, user_prompt] if p]).strip()
                self._last_audio_system_prompt = system_prompt
                self._last_audio_user_prompt = user_prompt
                self._last_audio_prompt = combined_prompt
                if self.logging_cfg.get('llm_raw', False):
                    max_len = int(self.logging_cfg.get('max_chars', 8000))
                    prefix = ''
                    if session_id or trace_id:
                        prefix = f"[session={session_id or ''} trace={trace_id or ''}] "
                    self.logger.info(f"{prefix}LM IN (audio/system): {system_prompt[:max_len]}")
                    self.logger.info(f"{prefix}LM IN (audio/user): {user_prompt[:max_len]}")
                mime_type = self._infer_mime_type(audio_file_path)
                content = {
                    "parts": [
                        {"text": system_prompt},
                        {"text": user_prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(audio_data).decode('utf-8')
                            }
                        }
                    ]
                }
            else:
                self._last_audio_used_dspy = False
                self._last_audio_signature = None
                self.logger.info("[DSPy] Skipped (prompt_via_dspy=false). Using legacy PromptManager audio prompt.")
                if self._prompt_manager is None:
                    from ..core.prompt_manager import PromptManager
                    self._prompt_manager = PromptManager()
                legacy_prompt = self._prompt_manager.get_audio_prompt(
                    character if use_context else None,
                    conversation_history if use_context else None,
                )
                self._last_audio_prompt = legacy_prompt
                self._last_audio_system_prompt = legacy_prompt
                self._last_audio_user_prompt = ""
                if self.logging_cfg.get('llm_raw', False):
                    max_len = int(self.logging_cfg.get('max_chars', 8000))
                    prefix = ''
                    if session_id or trace_id:
                        prefix = f"[session={session_id or ''} trace={trace_id or ''}] "
                    self.logger.info(f"{prefix}LM IN (audio): {legacy_prompt[:max_len]}")
                mime_type = self._infer_mime_type(audio_file_path)
                content = {
                    "parts": [
                        {"text": legacy_prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(audio_data).decode('utf-8')
                            }
                        }
                    ]
                }

            generation_config = {
                "temperature": 0.3,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 1024,
            }

            self.logger.info("調用 Gemini 多模態 API 進行音頻識別")
            response = self.multimodal_model.generate_content(
                content,
                generation_config=generation_config
            )

            result_text = response.text.strip()
            self._last_audio_raw = result_text
            self.logger.info("===== 音頻識別完成 =====")
            try:
                if self.logging_cfg.get('llm_raw', False):
                    max_len = int(self.logging_cfg.get('max_chars', 8000))
                    prefix = ''
                    if session_id or trace_id:
                        prefix = f"[session={session_id or ''} trace={trace_id or ''}] "
                    self.logger.info(f"{prefix}LM OUT (audio/raw): {result_text[:max_len]}")
                else:
                    self.logger.debug(f"識別結果: '{result_text[:100]}...'")
            except Exception:
                pass

            cleaned_text = result_text
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            try:
                json_result = json.loads(cleaned_text)

                # 驗證必要欄位（不降級，缺少則返回錯誤）
                raw_transcript = json_result.get('raw_transcript')
                keyword_completion = json_result.get('keyword_completion')
                original = json_result.get('original')
                options = json_result.get('options')

                # 嚴格驗證：必須包含 raw_transcript
                if raw_transcript is None:
                    self.logger.error("Gemini 返回格式錯誤：缺少 raw_transcript")
                    error_result = json.dumps({
                        "error": "格式錯誤：缺少 raw_transcript",
                        "raw_transcript": "",
                        "keyword_completion": [],
                        "original": "語音識別格式錯誤，請重試",
                        "options": ["語音識別格式錯誤，請重試"]
                    }, ensure_ascii=False)
                    self._last_audio_clean = error_result
                    return error_result

                # 嚴格驗證：必須包含 keyword_completion
                if keyword_completion is None or not isinstance(keyword_completion, list):
                    self.logger.error("Gemini 返回格式錯誤：缺少或無效的 keyword_completion")
                    error_result = json.dumps({
                        "error": "格式錯誤：缺少 keyword_completion",
                        "raw_transcript": raw_transcript or "",
                        "keyword_completion": [],
                        "original": "語音識別格式錯誤，請重試",
                        "options": ["語音識別格式錯誤，請重試"]
                    }, ensure_ascii=False)
                    self._last_audio_clean = error_result
                    return error_result

                # 保存到診斷屬性
                self._last_audio_raw_transcript = raw_transcript
                self._last_audio_keyword_completion = keyword_completion

                # 返回完整結構
                result = {
                    "raw_transcript": raw_transcript,
                    "keyword_completion": keyword_completion,
                    "original": original or "",
                    "options": options or []
                }
                self._last_audio_clean = json.dumps(result, ensure_ascii=False)

                if self.logging_cfg.get('llm_raw', False):
                    max_len = int(self.logging_cfg.get('max_chars', 8000))
                    prefix = ''
                    if session_id or trace_id:
                        prefix = f"[session={session_id or ''} trace={trace_id or ''}] "
                    self.logger.info(f"{prefix}LM OUT (audio/clean): {self._last_audio_clean[:max_len]}")
                return self._last_audio_clean
            except json.JSONDecodeError:
                self.logger.error(f"回應不是 JSON 格式: {result_text}")
                error_result = json.dumps({
                    "error": "JSON 解析錯誤",
                    "raw_transcript": "",
                    "keyword_completion": [],
                    "original": "語音識別格式錯誤，請重試",
                    "options": ["語音識別格式錯誤，請重試"]
                }, ensure_ascii=False)
                self._last_audio_clean = error_result
                return error_result

        except Exception as e:
            self.logger.error(f"音頻識別失敗: {e}", exc_info=True)
            return json.dumps({
                "original": "音頻識別過程中發生錯誤",
                "options": ["音頻識別過程中發生錯誤，請重試"]
            })

    @property
    def last_audio_prompt(self) -> Optional[str]:
        return self._last_audio_prompt

    @property
    def last_audio_system_prompt(self) -> Optional[str]:
        return self._last_audio_system_prompt

    @property
    def last_audio_user_prompt(self) -> Optional[str]:
        return self._last_audio_user_prompt

    @property
    def last_audio_template_rules(self) -> Optional[str]:
        return self._last_audio_template_rules

    @property
    def last_audio_raw(self) -> Optional[str]:
        return self._last_audio_raw

    @property
    def last_audio_clean(self) -> Optional[str]:
        return self._last_audio_clean

    @property
    def last_trace_id(self) -> Optional[str]:
        return self._last_trace_id

    @property
    def last_audio_raw_transcript(self) -> Optional[str]:
        return self._last_audio_raw_transcript

    @property
    def last_audio_keyword_completion(self) -> Optional[list]:
        return self._last_audio_keyword_completion
