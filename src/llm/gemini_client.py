from google import genai
from google.genai import types
from ..utils.config import load_config
import logging
import os
import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.audio.context_utils import (
    format_history_for_audio,
    build_available_audio_contexts,
    summarize_character,
    build_audio_template_rules,
)
from ..core.dspy.audio_modules import get_audio_prompt_composer
from ..utils.settings import DEFAULT_GEMINI_MODEL, get_gemini_model

class GeminiClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
    ):
        config = load_config()
        self.logger = logging.getLogger(__name__)

        # API key
        effective_api_key = api_key or config.get("google_api_key")
        self._client = genai.Client(api_key=effective_api_key)

        # Model name
        # Safety: if the user hasn't opted into the new `llm:` schema, keep the
        # historical default model to avoid behavior changes.
        raw_has_llm = bool((config.get("_meta") or {}).get("raw_has_llm"))
        if model:
            self.model_name = model
        elif raw_has_llm:
            self.model_name = get_gemini_model(config)
        else:
            self.model_name = DEFAULT_GEMINI_MODEL

        # Generation config
        default_generation_config: Dict[str, Any] = {
            "temperature": 0.9,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        if generation_config:
            merged = dict(default_generation_config)
            merged.update(generation_config)
            self.generation_config = merged
        else:
            llm_generation = ((config.get("llm") or {}).get("generation") or {}) if raw_has_llm else {}
            merged = dict(default_generation_config)
            if isinstance(llm_generation, dict):
                merged.update({k: v for k, v in llm_generation.items() if v is not None})
            self.generation_config = merged
        self.logging_cfg = config.get('logging', {}) or {}
        self.audio_cfg = config.get('audio', {}) or {}
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
        # Timing breakdown
        self._last_audio_timings: Optional[Dict[str, float]] = None
        
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
            self.logger.info("模型: %s", self.model_name)
            # 安全地處理 prompt 日誌
            if isinstance(prompt, str):
                self.logger.debug(f"提示詞: {prompt[:100]}... (截斷顯示)")
            else:
                self.logger.debug(f"提示詞類型: {type(prompt)}, 內容: {str(prompt)[:100]}... (截斷顯示)")
            
            # 設定生成參數以確保更好的格式控制
            generation_config = dict(self.generation_config)
            self.logger.info("生成參數: %s", generation_config)

            # thinking_budget for dialogue (from dspy config)
            dspy_cfg = load_config().get('dspy', {}) or {}
            thinking_budget = int(dspy_cfg.get('thinking_budget', 1024))

            # 呼叫 API
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=generation_config.get("temperature"),
                    top_p=generation_config.get("top_p"),
                    top_k=generation_config.get("top_k"),
                    max_output_tokens=generation_config.get("max_output_tokens"),
                    response_mime_type=generation_config.get("response_mime_type"),
                    safety_settings=[
                        types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                        types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                        types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                        types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                    ],
                    thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                ),
            )
            
            # 記錄 API 回傳的結果
            self.logger.info(f"===== 接收到 Gemini API 回應 =====")
            self.logger.debug(f"回應長度: {len(response.text)}")
            try:
                candidates = getattr(response, "candidates", None) or []
                finish_reason = None
                if candidates:
                    finish_reason = getattr(candidates[0], "finish_reason", None)
                prompt_feedback = getattr(response, "prompt_feedback", None)
                self.logger.info("Gemini finish_reason: %s", finish_reason)
                if prompt_feedback is not None:
                    self.logger.info("Gemini prompt_feedback: %s", prompt_feedback)
            except Exception:
                self.logger.debug("Failed to read Gemini finish_reason/prompt_feedback", exc_info=True)
            
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
            _t_start = time.time()
            _t_retry_start = _t_retry_end = None
            self._last_audio_timings = None

            if not os.path.exists(audio_file_path):
                self.logger.error(f"音頻文件不存在: {audio_file_path}")
                return json.dumps({
                    "original": "無法處理音頻文件：文件不存在",
                    "options": ["無法處理音頻文件：文件不存在"]
                })

            _t_audio_read_start = time.time()
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

            _t_audio_read_end = time.time()
            _t_prompt_compose_start = time.time()
            option_count = int(self.audio_cfg.get('option_count', 4) or 4)
            use_context = bool(self.audio_cfg.get('use_context', False))
            template_variant = str(self.audio_cfg.get("template_variant", "full")).lower()
            prompt_via_dspy_raw = self.audio_cfg.get('prompt_via_dspy', True)
            if prompt_via_dspy_raw is False:
                raise RuntimeError("Legacy audio prompt is removed; set audio.prompt_via_dspy=true.")

            # Diagnostics: log audio configuration
            self.logger.info(
                "[AudioCfg] prompt_via_dspy=%s, use_context=%s, option_count=%s",
                True, use_context, option_count,
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
            if template_variant in {"compact", "short", "lite"}:
                template_rules = ""

            self._last_trace_id = trace_id
            self._last_audio_template_rules = template_rules

            template_path = None
            template_path_raw = self.audio_cfg.get("template_path")
            if template_path_raw:
                template_path = Path(str(template_path_raw))
            else:
                if template_variant in {"compact", "short", "lite"}:
                    template_path = Path("prompts/templates/audio_disfluency_template_compact.yaml")
            composer = get_audio_prompt_composer(template_path=template_path)
            # Diagnostics: record and log signature/inputs presence
            sig_name = None
            try:
                sig_name = getattr(composer, 'signature').__name__  # type: ignore[attr-defined]
            except Exception:
                sig_name = str(getattr(composer, 'signature', 'unknown'))
            self._last_audio_used_dspy = True
            self._last_audio_signature = sig_name
            self.logger.info(
                "[DSPy] Using AudioPromptComposerModule (Signature=%s, template=%s) | profile_len=%s, history_len=%s, contexts_len=%s, rules_len=%s",
                sig_name,
                template_path.name if template_path else "default",
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

            audio_max_tokens = int(self.audio_cfg.get("max_output_tokens", 1024) or 1024)
            audio_thinking_budget = int(self.audio_cfg.get('thinking_budget', 0))

            _t_prompt_compose_end = time.time()
            _t_gemini_api_start = time.time()
            self.logger.info("調用 Gemini 多模態 API 進行音頻識別")
            self.logger.info("音頻識別參數: max_output_tokens=%s, thinking_budget=%s", audio_max_tokens, audio_thinking_budget)
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=[
                    system_prompt,
                    user_prompt,
                    types.Part.from_bytes(data=audio_data, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=audio_max_tokens,
                    response_mime_type="application/json",
                    thinking_config=types.ThinkingConfig(thinking_budget=audio_thinking_budget),
                ),
            )

            _t_gemini_api_end = time.time()
            _t_json_parse_start = time.time()
            result_text = response.text.strip()
            self._last_audio_raw = result_text
            self.logger.info("===== 音頻識別完成 =====")
            try:
                candidates = getattr(response, "candidates", None) or []
                finish_reason = None
                if candidates:
                    finish_reason = getattr(candidates[0], "finish_reason", None)
                prompt_feedback = getattr(response, "prompt_feedback", None)
                self.logger.info("Gemini (audio) finish_reason: %s", finish_reason)
                if prompt_feedback is not None:
                    self.logger.info("Gemini (audio) prompt_feedback: %s", prompt_feedback)
            except Exception:
                self.logger.debug("Failed to read Gemini audio finish_reason/prompt_feedback", exc_info=True)
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

            def _clean_json_payload(payload: str) -> str:
                cleaned = payload.strip()
                if cleaned.startswith('```json'):
                    cleaned = cleaned[7:]
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3]
                return cleaned.strip()

            def _parse_audio_json(payload: str) -> Optional[dict]:
                cleaned = _clean_json_payload(payload)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    return None

            json_result = _parse_audio_json(result_text)
            _t_json_parse_end = time.time()
            if json_result is None:
                self.logger.warning("音頻 JSON 解析失敗，嘗試重新請求更精簡輸出")
                self.logger.warning("[Timing][retry_trigger] first parse failed, raw_snippet=%s", result_text[:200])
                fallback_prompt = (
                    "請直接輸出單一合法 JSON，不要任何 Markdown 或說明文字。\n"
                    "格式如下：\n"
                    "{\n"
                    f"  \"raw_transcript\": \"完整轉錄，用...分隔，若不清楚寫無法識別\",\n"
                    "  \"keyword_completion\": [\n"
                    "    {\"heard\": \"片段\", \"completed\": \"補全詞\", \"confidence\": \"high/medium/low\", \"reason\": \"\"}\n"
                    "  ],\n"
                    "  \"original\": \"根據補全詞組成的短句\",\n"
                    f"  \"options\": [\"句子1\", \"句子2\", \"句子3\", \"句子4\"]\n"
                    "}\n"
                    "限制：keyword_completion 最多 8 個項目；options 必須恰好 4 句。\n"
                    "若無法識別，輸出：\n"
                    "{\"raw_transcript\":\"無法識別\",\"keyword_completion\":[],\"original\":\"無法識別\",\"options\":[\"我需要協助重新表達剛才的需求\",\"能否請您幫我重述或慢一點說\",\"我想請對方幫我確認我剛才想表達的事情\",\"我需要協助確認我的需要，謝謝\"]}\n\n"
                    f"以下是上一次模型回傳的原始文字，請據此重新輸出合法 JSON：\n{result_text[:2000]}"
                )
                _t_retry_start = time.time()
                retry_response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=fallback_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=audio_max_tokens,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                _t_retry_end = time.time()
                retry_text = retry_response.text.strip()
                self.logger.info("===== 音頻識別重試完成 =====")
                try:
                    candidates = getattr(retry_response, "candidates", None) or []
                    finish_reason = None
                    if candidates:
                        finish_reason = getattr(candidates[0], "finish_reason", None)
                    self.logger.info("Gemini (audio retry) finish_reason: %s", finish_reason)
                except Exception:
                    self.logger.debug("Failed to read Gemini audio retry finish_reason", exc_info=True)
                if self.logging_cfg.get('llm_raw', False):
                    max_len = int(self.logging_cfg.get('max_chars', 8000))
                    prefix = ''
                    if session_id or trace_id:
                        prefix = f"[session={session_id or ''} trace={trace_id or ''}] "
                    self.logger.info(f"{prefix}LM OUT (audio/raw/retry): {retry_text[:max_len]}")
                json_result = _parse_audio_json(retry_text)
                if json_result is None:
                    self.logger.error("重試後仍無法解析音頻 JSON")
                    json_result = None

            if json_result is not None:

                # 驗證必要欄位（不降級，缺少則返回錯誤）
                raw_transcript = json_result.get('raw_transcript')
                keyword_completion = json_result.get('keyword_completion')
                original = json_result.get('original')
                options = json_result.get('options')

                # 嚴格驗證：必須包含 raw_transcript
                if raw_transcript is None:
                    self.logger.error("Gemini 返回格式錯誤：缺少 raw_transcript")
                    json_result = None

                # 嚴格驗證：必須包含 keyword_completion
                if json_result is not None and (keyword_completion is None or not isinstance(keyword_completion, list)):
                    self.logger.error("Gemini 返回格式錯誤：缺少或無效的 keyword_completion")
                    json_result = None

                if json_result is None:
                    _t_end = time.time()
                    _retry_triggered = _t_retry_start is not None and _t_retry_end is not None
                    self._last_audio_timings = {
                        "audio_read_s": round(_t_audio_read_end - _t_audio_read_start, 4),
                        "prompt_compose_s": round(_t_prompt_compose_end - _t_prompt_compose_start, 4),
                        "gemini_api_call_s": round(_t_gemini_api_end - _t_gemini_api_start, 4),
                        "json_parse_s": round(_t_json_parse_end - _t_json_parse_start, 4),
                        "total_s": round(_t_end - _t_start, 4),
                        "retry_triggered": _retry_triggered,
                        "error": "field_validation_failed",
                    }
                    if _retry_triggered:
                        self._last_audio_timings["gemini_retry_s"] = round(_t_retry_end - _t_retry_start, 4)
                    self.logger.info("[Timing] transcribe_audio (error): %s", self._last_audio_timings)
                    error_result = json.dumps({
                        "error": "格式錯誤：缺少必要欄位",
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

                _t_end = time.time()
                _retry_triggered = _t_retry_start is not None and _t_retry_end is not None
                self._last_audio_timings = {
                    "audio_read_s": round(_t_audio_read_end - _t_audio_read_start, 4),
                    "prompt_compose_s": round(_t_prompt_compose_end - _t_prompt_compose_start, 4),
                    "gemini_api_call_s": round(_t_gemini_api_end - _t_gemini_api_start, 4),
                    "json_parse_s": round(_t_json_parse_end - _t_json_parse_start, 4),
                    "total_s": round(_t_end - _t_start, 4),
                    "retry_triggered": _retry_triggered,
                }
                if _retry_triggered:
                    self._last_audio_timings["gemini_retry_s"] = round(_t_retry_end - _t_retry_start, 4)
                self.logger.info("[Timing] transcribe_audio: %s", self._last_audio_timings)
                return self._last_audio_clean

            self.logger.error(f"回應不是 JSON 格式: {result_text}")
            _t_end = time.time()
            _retry_triggered = _t_retry_start is not None and _t_retry_end is not None
            self._last_audio_timings = {
                "audio_read_s": round(_t_audio_read_end - _t_audio_read_start, 4),
                "prompt_compose_s": round(_t_prompt_compose_end - _t_prompt_compose_start, 4),
                "gemini_api_call_s": round(_t_gemini_api_end - _t_gemini_api_start, 4),
                "json_parse_s": round(_t_json_parse_end - _t_json_parse_start, 4),
                "total_s": round(_t_end - _t_start, 4),
                "retry_triggered": _retry_triggered,
                "error": "json_parse_failed",
            }
            if _retry_triggered:
                self._last_audio_timings["gemini_retry_s"] = round(_t_retry_end - _t_retry_start, 4)
            self.logger.info("[Timing] transcribe_audio (error): %s", self._last_audio_timings)
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
