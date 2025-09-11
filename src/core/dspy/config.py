"""
DSPy 配置管理模組

負責管理 DSPy 的初始化、配置載入和全局設置。
"""

import yaml
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DSPyConfig:
    """DSPy 配置管理類"""
    
    def __init__(self, config_path: str = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路徑，默認使用專案中的 config.yaml
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), 
                '..', '..', '..', 
                'config', 'config.yaml'
            )
        
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
        self._dspy_config: Optional[Dict[str, Any]] = None
        
    def load_config(self) -> Dict[str, Any]:
        """載入配置文件
        
        Returns:
            完整的配置字典
        """
        if self._config is None:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f)
                logger.debug(f"成功載入配置文件: {self.config_path}")
            except FileNotFoundError:
                logger.error(f"配置文件不存在: {self.config_path}")
                self._config = {}
            except yaml.YAMLError as e:
                logger.error(f"解析配置文件失敗: {e}")
                self._config = {}
        
        return self._config
    
    def get_dspy_config(self) -> Dict[str, Any]:
        """獲取 DSPy 相關配置
        
        Returns:
            DSPy 配置字典
        """
        if self._dspy_config is None:
            config = self.load_config()
            self._dspy_config = config.get('dspy', {})
            
            # 設置默認值
            defaults = {
                'enabled': False,
                'optimize': False,
                'model': 'gemini-2.0-flash-exp',
                'temperature': 0.9,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,
                'ab_testing': {
                    'enabled': False,
                    'percentage': 50
                },
                'caching': {
                    'enabled': True,
                    'ttl': 3600
                }
            }
            
            # 合併默認配置
            for key, default_value in defaults.items():
                if key not in self._dspy_config:
                    self._dspy_config[key] = default_value
                elif isinstance(default_value, dict):
                    for sub_key, sub_default in default_value.items():
                        if sub_key not in self._dspy_config[key]:
                            self._dspy_config[key][sub_key] = sub_default
        
        return self._dspy_config
    
    def is_dspy_enabled(self) -> bool:
        """檢查是否啟用 DSPy
        
        Returns:
            True 如果啟用 DSPy
        """
        return self.get_dspy_config().get('enabled', False)
    
    def is_optimization_enabled(self) -> bool:
        """檢查是否啟用提示優化
        
        Returns:
            True 如果啟用優化
        """
        return self.get_dspy_config().get('optimize', False)
    
    def get_model_config(self) -> Dict[str, Any]:
        """獲取模型配置
        
        Returns:
            模型配置字典
        """
        dspy_config = self.get_dspy_config()
        return {
            'model': dspy_config.get('model', 'gemini-2.0-flash-exp'),
            'temperature': dspy_config.get('temperature', 0.9),
            'top_p': dspy_config.get('top_p', 0.8),
            'top_k': dspy_config.get('top_k', 40),
            'max_output_tokens': dspy_config.get('max_output_tokens', 2048)
        }
    
    def get_ab_testing_config(self) -> Dict[str, Any]:
        """獲取 A/B 測試配置
        
        Returns:
            A/B 測試配置字典
        """
        return self.get_dspy_config().get('ab_testing', {
            'enabled': False,
            'percentage': 50
        })
    
    def get_caching_config(self) -> Dict[str, Any]:
        """獲取緩存配置
        
        Returns:
            緩存配置字典
        """
        return self.get_dspy_config().get('caching', {
            'enabled': True,
            'ttl': 3600
        })
    
    def get_google_api_key(self) -> str:
        """獲取 Google API Key
        
        Returns:
            Google API Key 字符串
        """
        config = self.load_config()
        return config.get('google_api_key', '')
    
    def reload_config(self) -> None:
        """重新載入配置（清除緩存）"""
        self._config = None
        self._dspy_config = None
        logger.info("配置緩存已清除，將在下次訪問時重新載入")

# 全局配置實例
_global_config = None

def get_config() -> DSPyConfig:
    """獲取全局配置實例
    
    Returns:
        DSPyConfig 實例
    """
    global _global_config
    if _global_config is None:
        _global_config = DSPyConfig()
    return _global_config

def reload_global_config() -> None:
    """重新載入全局配置"""
    global _global_config
    if _global_config:
        _global_config.reload_config()
    else:
        _global_config = DSPyConfig()

# 便捷函數
def is_dspy_enabled() -> bool:
    """檢查是否啟用 DSPy"""
    return get_config().is_dspy_enabled()

def get_model_config() -> Dict[str, Any]:
    """獲取模型配置"""
    return get_config().get_model_config()

def get_google_api_key() -> str:
    """獲取 Google API Key"""
    return get_config().get_google_api_key()