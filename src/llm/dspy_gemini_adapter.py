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

logger = logging.getLogger(__name__)

class DSPyGeminiLM(dspy.LM):
    """DSPy Gemini Language Model 適配器
    
    繼承 dspy.LM 並實現必要的方法，將 DSPy 的調用轉換為 Gemini API 調用。
    """
    
    def __init__(self, 
                 model: str = "gemini-2.0-flash-exp",
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
    
    def basic_request(self, prompt: str, **kwargs) -> str:
        """基本請求方法 - DSPy 必需
        
        Args:
            prompt: 輸入提示
            **kwargs: 其他參數
            
        Returns:
            模型回應字符串
        """
        return self._call_gemini(prompt, **kwargs)
    
    def __call__(self, prompt: Union[str, List[str]], **kwargs) -> Union[str, List[str]]:
        """主要調用方法 - DSPy 的標準接口
        
        Args:
            prompt: 輸入提示，可以是字符串或字符串列表
            **kwargs: 其他參數
            
        Returns:
            回應，可以是字符串或字符串列表
        """
        start_time = time.time()
        
        try:
            # 處理單個提示
            if isinstance(prompt, str):
                response = self._call_gemini(prompt, **kwargs)
                self._update_stats(start_time, success=True)
                return response
            
            # 處理多個提示
            elif isinstance(prompt, list):
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
            
            # 調用現有的 GeminiClient
            response = self.gemini_client.generate_response(prompt)
            
            # 記錄成功
            logger.debug(f"Gemini 回應長度: {len(response)} 字符")
            
            return response
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Gemini API 調用失敗 (第 {self.call_count} 次): {e}")
            
            # 返回錯誤回應（保持與原系統一致）
            error_response = '{"responses": ["抱歉，我現在無法正確回應"],"state": "CONFUSED","dialogue_context": "系統錯誤"}'
            return error_response
    
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