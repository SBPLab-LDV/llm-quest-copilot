"""
DSPy Gemini 適配器

將現有的 GeminiClient 包裝為 DSPy LM 接口，
保持所有現有的錯誤處理邏輯。
"""

import dspy
import logging
import json
import time
from typing import List, Dict, Any, Optional, Union
from .gemini_client import GeminiClient
from ..core.dspy.config import get_config

# DSPy 回應對象，確保與 DSPy 適配器兼容
class DSPyResponse:
    """DSPy 兼容的回應對象"""
    def __init__(self, text: str):
        self.text = text
    
    def __str__(self):
        return self.text
    
    def __repr__(self):
        return f"DSPyResponse(text='{self.text[:50]}...')"

logger = logging.getLogger(__name__)

# Ensure a dedicated debug log file exists for prompt/response inspection
try:
    _has_dspy_file_handler = any(
        isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '').endswith('dspy_internal_debug.log')
        for h in logger.handlers
    )
    if not _has_dspy_file_handler:
        _fh = logging.FileHandler('dspy_internal_debug.log', mode='a', encoding='utf-8')
        _fh.setLevel(logging.INFO)
        _fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(_fh)
except Exception:
    # Do not block if file handler cannot be configured
    pass

class DSPyGeminiLM(dspy.LM):
    """DSPy Gemini Language Model 適配器
    
    繼承 dspy.LM 並實現必要的方法，將 DSPy 的調用轉換為 Gemini API 調用。
    確保完全兼容 DSPy 的響應處理機制。
    """
    
    def __init__(self, 
                 model: str = "gemini-2.0-flash",
                 temperature: float = 0.9,
                 top_p: float = 0.8,
                 top_k: int = 40,
                 max_output_tokens: int = 2048,
                 **kwargs):
        """初始化 DSPy Gemini 適配器
        
        Args:
            model: 模型名稱
            temperature: 溫度參數
            top_p: top_p 參數
            top_k: top_k 參數
            max_output_tokens: 最大輸出 tokens
            **kwargs: 其他參數
        """
        # 調用父類初始化
        super().__init__(model=model, **kwargs)
        
        # 保存模型參數
        self.model_name = model
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_output_tokens = max_output_tokens
        
        # 創建 Gemini 客戶端實例
        self.gemini_client = GeminiClient()
        
        # 統計信息
        self.call_count = 0
        self.total_tokens = 0
        self.error_count = 0
        
        logger.info(f"DSPy Gemini 適配器初始化完成：模型={model}, 溫度={temperature}")
    
    def forward(self, prompt=None, messages=None, **kwargs):
        """DSPy LM 的核心 forward 方法 - 必須正確實現
        
        這是 DSPy 內部適配器調用的關鍵方法。我們必須返回
        DSPy 期望的回應格式。
        
        Args:
            prompt: 字符串提示
            messages: 消息列表（ChatML 格式）
            **kwargs: 其他參數
            
        Returns:
            DSPy 期望的回應格式
        """
        logger.info(f"🔄 DSPy forward() 調用")
        logger.info(f"  - prompt: {prompt[:100] if prompt else None}...")
        logger.info(f"  - messages: {messages}")
        logger.info(f"  - kwargs: {list(kwargs.keys())}")
        
        try:
            # 處理輸入格式
            if prompt is not None:
                input_text = prompt
            elif messages is not None:
                # 將 ChatML 消息轉換為單個提示
                input_text = self._convert_messages_to_prompt(messages)
            else:
                raise ValueError("必須提供 prompt 或 messages")
            
            logger.info(f"  - 處理後輸入: {input_text[:200]}...")
            
            # 調用我們的 Gemini 客戶端
            response_text = self._call_gemini(input_text, **kwargs)
            
            logger.info(f"🔄 DSPy forward() Gemini 回應長度: {len(response_text)}")
            logger.info(f"🔄 DSPy forward() Gemini 回應內容: {response_text[:200]}...")
            
            # 返回 DSPy 期望的回應格式
            # DSPy 期望一個字符串或具有 .choices 屬性的對象
            return response_text
            
        except Exception as e:
            logger.error(f"❌ DSPy forward() 失敗: {e}")
            import traceback
            logger.error(f"完整錯誤: {traceback.format_exc()}")
            raise
    
    def generate(self, prompt: str, **kwargs) -> str:
        """DSPy 期望的生成方法 - 確保兼容性
        
        Args:
            prompt: 輸入提示
            **kwargs: 其他參數
            
        Returns:
            模型回應字符串
        """
        logger.info(f"🔄 DSPy generate() 調用，prompt 長度: {len(prompt)}")
        logger.info(f"🔄 DSPy generate() prompt 內容: {prompt[:200]}...")
        response = self._call_gemini(prompt, **kwargs)
        logger.info(f"🔄 DSPy generate() 返回，response 長度: {len(response)}")
        logger.info(f"🔄 DSPy generate() 返回內容: {response[:200]}...")
        
        # 確保返回的是純字符串
        if not isinstance(response, str):
            logger.warning(f"⚠️ generate() 返回的不是字符串類型: {type(response)}")
            response = str(response)
        
        return response
    
    def basic_request(self, prompt: str, **kwargs) -> str:
        """基本請求方法 - DSPy 必需
        
        Args:
            prompt: 輸入提示
            **kwargs: 其他參數
            
        Returns:
            模型回應字符串
        """
        return self._call_gemini(prompt, **kwargs)
    
    def __call__(self, prompt: Union[str, List[str]] = None, **kwargs) -> Union[str, List[str]]:
        """主要調用方法 - DSPy 的標準接口
        
        CRITICAL: 這個方法被 DSPy 適配器直接調用！
        
        重要：我們不調用 super().__call__()，而是直接實現完整的調用流程，
        避免 DSPy 基類的複雜邏輯導致回應截斷。
        
        Args:
            prompt: 輸入提示，可以是字符串或字符串列表
            **kwargs: 其他參數
            
        Returns:
            回應，可以是字符串或字符串列表
        """
        start_time = time.time()
        
        logger.critical(f"🚨 DSPyGeminiLM.__call__ 被調用!")
        logger.critical(f"  - prompt type: {type(prompt)}")
        logger.critical(f"  - prompt: {prompt[:100] if isinstance(prompt, str) else prompt}...")
        logger.critical(f"  - kwargs keys: {list(kwargs.keys())}")
        
        try:
            # 檢查是否缺少 prompt
            if prompt is None:
                logger.warning("DSPyGeminiLM.__call__ 收到 None prompt，檢查 kwargs")
                logger.info(f"=== KWARGS 詳細內容檢查 ===")
                for key, value in kwargs.items():
                    logger.info(f"  {key}: {str(value)[:200]}...")
                logger.info(f"=== END KWARGS 詳細內容 ===")
                
                # 嘗試從 kwargs 中獲取 prompt - 增強版
                if 'messages' in kwargs:
                    # 處理 ChatML 格式的 messages
                    messages = kwargs['messages']
                    prompt = self._convert_messages_to_prompt(messages)
                    logger.info(f"從 messages 提取 prompt: {prompt[:200]}...")
                elif 'query' in kwargs:
                    prompt = kwargs['query']
                    logger.info(f"從 query 提取 prompt: {prompt[:200]}...")
                elif 'text' in kwargs:
                    prompt = kwargs['text']
                    logger.info(f"從 text 提取 prompt: {prompt[:200]}...")
                elif 'prompt' in kwargs:
                    prompt = kwargs['prompt']
                    logger.info(f"從 prompt 參數提取: {prompt[:200]}...")
                else:
                    logger.error(f"無法從任何 kwargs 參數中找到 prompt！")
                    logger.error(f"可用的 kwargs 鍵: {list(kwargs.keys())}")
                    raise ValueError("未找到 prompt 參數，無法處理請求")
            
            # 處理單個提示
            if isinstance(prompt, str):
                logger.debug(f"處理單個提示: {prompt[:100]}...")
                response = self._call_gemini(prompt, **kwargs)
                self._update_stats(start_time, success=True)
                
                # ===== DSPy 接口修復 =====
                # 確保返回的響應格式符合 DSPy 預期
                logger.info(f"🔧 DSPy 接口修復 - 返回響應長度: {len(response)} 字符")
                logger.info(f"🔧 DSPy 接口修復 - 返回響應內容: {response}")
                
                # 最終類型檢查
                if not isinstance(response, str):
                    logger.error(f"❌ __call__ 返回非字符串類型: {type(response)}")
                    response = str(response)
                
                # 返回列表[str]，符合 DSPy adapters 對批量/單一回應的期望，避免被當作字元序列處理
                logger.critical(f"🔧 Adapter 兼容性修復 - 返回列表[str] 以避免截斷")
                logger.critical(f"  - 回應長度: {len(response)} 字符")
                logger.critical(f"  - 回應前100字符: {response[:100]}...")
                return [response]
            
            # 處理多個提示
            elif isinstance(prompt, list):
                logger.debug(f"處理批量提示: {len(prompt)} 個")
                responses = []
                for p in prompt:
                    response = self._call_gemini(p, **kwargs)
                    responses.append(response)
                self._update_stats(start_time, success=True, batch_size=len(prompt))
                return responses
            
            else:
                raise ValueError(f"不支持的 prompt 類型: {type(prompt)}")
                
        except Exception as e:
            self._update_stats(start_time, success=False)
            logger.error(f"DSPy Gemini 調用失敗: {e}")
            raise
    
    def _convert_messages_to_prompt(self, messages) -> str:
        """將 ChatML 格式的 messages 轉換為單個 prompt 字符串
        
        Args:
            messages: ChatML 格式的消息列表
            
        Returns:
            合併後的 prompt 字符串
        """
        if isinstance(messages, list):
            prompt_parts = []
            for msg in messages:
                if isinstance(msg, dict) and 'content' in msg:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    
                    if role == 'system':
                        prompt_parts.append(f"System: {content}")
                    elif role == 'user':
                        prompt_parts.append(f"User: {content}")
                    elif role == 'assistant':
                        prompt_parts.append(f"Assistant: {content}")
                    else:
                        prompt_parts.append(content)
                else:
                    prompt_parts.append(str(msg))
            
            return "\n\n".join(prompt_parts)
        else:
            return str(messages)
    
    def _call_gemini(self, prompt: str, **kwargs) -> str:
        """調用 Gemini API
        
        Args:
            prompt: 輸入提示
            **kwargs: 其他參數
            
        Returns:
            Gemini 回應
        """
        self.call_count += 1
        
        try:
            logger.debug(f"DSPy -> Gemini 調用 #{self.call_count}")
            logger.debug(f"提示長度: {len(prompt)} 字符")
            
            # ====== 詳細日誌追蹤 - GEMINI PROMPT INPUT ======
            logger.info(f"=== GEMINI PROMPT INPUT (Call #{self.call_count}) ===")
            logger.info(f"Prompt length: {len(prompt)} characters")
            logger.info(f"Full prompt content:\n{prompt}")
            logger.info(f"Call kwargs: {kwargs}")
            logger.info(f"=== END GEMINI PROMPT INPUT ===")
            
            # 調用現有的 GeminiClient
            response = self.gemini_client.generate_response(prompt)
            
            # ====== 詳細日誌追蹤 - GEMINI RESPONSE OUTPUT ======
            logger.info(f"=== GEMINI RESPONSE OUTPUT (Call #{self.call_count}) ===")
            logger.info(f"Response length: {len(response)} characters")
            logger.info(f"Full response content:\n{response}")
            logger.info(f"=== END GEMINI RESPONSE OUTPUT ===")
            
            # 清理 markdown 代碼塊格式 (為了DSPy JSON適配器)
            cleaned_response = self._clean_markdown_json(response)
            
            if cleaned_response != response:
                logger.info(f"🧹 清理 markdown 格式: {len(response)} -> {len(cleaned_response)} 字符")
                logger.info(f"清理後完整內容: {cleaned_response}")
                logger.debug(f"清理後內容: {cleaned_response[:200]}...")
            
            # 正規化 JSON：確保所有必填鍵存在，避免 JSONAdapter 解析失敗
            normalized_response = self._normalize_json_response(cleaned_response)
            
            logger.debug(f"Gemini 回應長度: {len(normalized_response)} 字符")
            return normalized_response
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Gemini API 調用失敗 (第 {self.call_count} 次): {e}")
            
            # 返回完整鍵集合的錯誤回應，避免 JSONAdapter 解析失敗
            fallback = {
                "reasoning": "系統錯誤，使用安全回退。",
                "character_consistency_check": "NO",
                "context_classification": "unknown",
                "confidence": "0.00",
                "responses": ["抱歉，我現在無法正確回應"],
                "state": "CONFUSED",
                "dialogue_context": "系統錯誤",
                "state_reasoning": "LLM 調用異常，啟用回退。"
            }
            return json.dumps(fallback, ensure_ascii=False)
    
    def _clean_markdown_json(self, response: str) -> str:
        """清理 Gemini 回應中的 markdown 代碼塊格式
        
        DSPy JSON 適配器期望純 JSON，但 Gemini 經常返回 markdown 格式的 JSON
        
        Args:
            response: Gemini 的原始回應
            
        Returns:
            清理後的回應
        """
        import re
        
        # 移除 markdown 代碼塊標記
        # 匹配 ```json ... ``` 或 ``` ... ```
        cleaned = re.sub(r'^```(?:json)?\s*\n', '', response.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'\n```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
        
        # 移除前後的空白
        cleaned = cleaned.strip()
        
        # 如果結果是有效的 JSON 格式，返回清理後的版本
        try:
            import json
            json.loads(cleaned)  # 測試是否為有效 JSON
            return cleaned
        except json.JSONDecodeError:
            # 如果清理後不是有效 JSON，返回原始回應
            logger.warning(f"清理後的回應不是有效 JSON，返回原始回應")
            return response

    def _normalize_json_response(self, text: str) -> str:
        """嘗試將回應正規化為包含所有必填鍵的 JSON。
        - 僅在回應看起來像 JSON 物件時動作；否則原樣返回。
        - 確保缺失鍵以安全預設補齊，避免 JSONAdapter 解析中斷。
        """
        try:
            s = text.strip()
            if not (s.startswith('{') and s.endswith('}')):
                return text

            obj = json.loads(s)
            if not isinstance(obj, dict):
                return text

            required = [
                "reasoning",
                "character_consistency_check",
                "context_classification",
                "confidence",
                "responses",
                "state",
                "dialogue_context",
                "state_reasoning"
            ]

            # 補齊缺失鍵
            defaults = {
                "reasoning": "",
                "character_consistency_check": "YES",
                "context_classification": "daily_routine_examples",
                "confidence": "0.90",
                "responses": ["我明白了，請繼續。"],
                "state": "NORMAL",
                "dialogue_context": "對話進行中",
                "state_reasoning": "自動補齊缺失鍵以維持格式完整"
            }

            for k in required:
                if k not in obj or obj[k] in (None, ""):
                    obj[k] = defaults[k]

            # 規範 responses 類型
            if isinstance(obj.get("responses"), str):
                try:
                    maybe_list = json.loads(obj["responses"])  # 字串形式的 JSON 陣列
                    if isinstance(maybe_list, list):
                        obj["responses"] = [str(x) for x in maybe_list[:5]]
                    else:
                        obj["responses"] = [obj["responses"]]
                except Exception:
                    obj["responses"] = [obj["responses"]]
            elif isinstance(obj.get("responses"), list):
                obj["responses"] = [str(x) for x in obj["responses"][:5]]
            else:
                obj["responses"] = [str(obj["responses"])]

            # 規範 confidence 為帶兩位小數的字串
            conf = obj.get("confidence", "0.90")
            try:
                conf_f = float(conf)
            except Exception:
                conf_f = 0.90
            obj["confidence"] = f"{conf_f:.2f}"

            # 約束 state
            valid_states = {"NORMAL", "CONFUSED", "TRANSITIONING", "TERMINATED"}
            if str(obj.get("state", "")).upper() not in valid_states:
                obj["state"] = "NORMAL"

            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            return text
    
    def _process_lm_response(self, response, prompt=None, messages=None, **kwargs):
        """處理 LM 回應 - DSPy 基類調用的關鍵方法
        
        這個方法被 DSPy 基類在 __call__ 中調用來處理 LM 的原始回應。
        如果沒有正確實現，會導致回應被截斷。
        
        Args:
            response: 我們 forward() 方法返回的原始回應
            prompt: 原始 prompt
            messages: 原始 messages
            **kwargs: 其他參數
            
        Returns:
            處理後的回應，供 DSPy 適配器使用
        """
        logger.critical(f"🔧 _process_lm_response 被調用!")
        logger.critical(f"  - response type: {type(response)}")
        logger.critical(f"  - response length: {len(str(response))}")
        logger.critical(f"  - response content: {str(response)[:200]}...")
        
        try:
            # 如果回應是字符串，直接返回
            if isinstance(response, str):
                logger.info(f"✅ _process_lm_response 返回字符串回應")
                return response
                
            # 如果回應是列表，處理第一個元素
            elif isinstance(response, list) and len(response) > 0:
                first_response = str(response[0])
                logger.info(f"✅ _process_lm_response 從列表返回第一個元素")
                return first_response
                
            # 如果回應有 choices 屬性（LiteLLM 格式）
            elif hasattr(response, 'choices') and len(response.choices) > 0:
                content = response.choices[0].message.content
                logger.info(f"✅ _process_lm_response 從 LiteLLM 格式提取內容")
                return content
                
            # 如果回應有 text 屬性
            elif hasattr(response, 'text'):
                text_content = response.text
                logger.info(f"✅ _process_lm_response 從 text 屬性提取內容")
                return text_content
                
            # 其他情況，轉換為字符串
            else:
                str_response = str(response)
                logger.warning(f"⚠️ _process_lm_response 未知格式，轉換為字符串: {type(response)}")
                return str_response
                
        except Exception as e:
            logger.error(f"❌ _process_lm_response 處理失敗: {e}")
            # 緊急情況下返回原始回應的字符串版本
            return str(response) if response is not None else ""
    
    def _update_stats(self, start_time: float, success: bool, batch_size: int = 1):
        """更新統計信息
        
        Args:
            start_time: 開始時間
            success: 是否成功
            batch_size: 批次大小
        """
        duration = time.time() - start_time
        
        if success:
            logger.debug(f"DSPy Gemini 調用成功，耗時 {duration:.2f}s")
        else:
            logger.warning(f"DSPy Gemini 調用失敗，耗時 {duration:.2f}s")
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計信息
        
        Returns:
            統計信息字典
        """
        return {
            "model": self.model_name,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.call_count, 1),
            "total_tokens": self.total_tokens
        }
    
    def reset_stats(self):
        """重置統計信息"""
        self.call_count = 0
        self.total_tokens = 0
        self.error_count = 0
        logger.info("DSPy Gemini 統計信息已重置")
    
    @classmethod
    def from_config(cls, config_override: Optional[Dict[str, Any]] = None) -> 'DSPyGeminiLM':
        """從配置創建實例
        
        Args:
            config_override: 配置覆寫
            
        Returns:
            DSPyGeminiLM 實例
        """
        config = get_config()
        model_config = config.get_model_config()
        
        # 應用配置覆寫
        if config_override:
            model_config.update(config_override)
        
        return cls(**model_config)

def create_dspy_lm(config_override: Optional[Dict[str, Any]] = None) -> DSPyGeminiLM:
    """創建 DSPy Language Model 實例
    
    Args:
        config_override: 配置覆寫
        
    Returns:
        DSPyGeminiLM 實例
    """
    return DSPyGeminiLM.from_config(config_override)

# 測試函數
def test_dspy_gemini_adapter():
    """測試 DSPy Gemini 適配器"""
    logger.info("測試 DSPy Gemini 適配器...")
    
    try:
        # 創建適配器實例
        lm = create_dspy_lm()
        
        # 測試單個提示
        test_prompt = "Hello, this is a test prompt."
        response = lm(test_prompt)
        
        logger.info(f"測試提示: {test_prompt}")
        logger.info(f"回應: {response[:100]}...")
        
        # 測試統計信息
        stats = lm.get_stats()
        logger.info(f"統計信息: {stats}")
        
        logger.info("DSPy Gemini 適配器測試成功")
        return True
        
    except Exception as e:
        logger.error(f"DSPy Gemini 適配器測試失敗: {e}")
        return False

if __name__ == "__main__":
    # 設置日誌
    logging.basicConfig(level=logging.INFO)
    
    # 運行測試
    test_dspy_gemini_adapter()
