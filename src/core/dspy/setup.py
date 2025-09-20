"""
DSPy 初始化和設置模組

負責初始化 DSPy 環境、配置全局設置，以及管理 DSPy 的生命週期。
"""

import dspy
import logging
from typing import Dict, Any, Optional, List
from .config import get_config
from ...llm.dspy_gemini_adapter import DSPyGeminiLM
from ...llm.dspy_ollama_adapter import DSPyOllamaLM

logger = logging.getLogger(__name__)

class DSPyManager:
    """DSPy 管理器
    
    負責管理 DSPy 的初始化、配置和生命週期。
    """
    
    def __init__(self):
        self._is_initialized = False
        self._lm_instance: Optional[DSPyGeminiLM] = None
        self._settings: Optional[Dict[str, Any]] = None
    
    def initialize(self, config_override: Optional[Dict[str, Any]] = None) -> bool:
        """初始化 DSPy 環境
        
        Args:
            config_override: 配置覆寫
            
        Returns:
            是否初始化成功
        """
        if self._is_initialized:
            logger.info("DSPy 已經初始化，跳過重複初始化")
            return True
        
        try:
            logger.info("開始初始化 DSPy 環境...")
            
            # 載入配置
            config = get_config()
            dspy_config = config.get_dspy_config()
            
            # 應用配置覆寫
            if config_override:
                dspy_config.update(config_override)
            
            # 創建 Language Model 實例
            model_config = config.get_model_config()
            if config_override and 'model_config' in config_override:
                model_config.update(config_override['model_config'])

            provider = model_config.pop('provider', 'gemini').lower()

            if provider == 'ollama':
                self._lm_instance = DSPyOllamaLM(**model_config)
                logger.info("創建 DSPy Ollama LM: %s", model_config)
            else:
                self._lm_instance = DSPyGeminiLM(**model_config)
                logger.info("創建 DSPy Gemini LM: %s", model_config)
            
            # 配置 DSPy 全局設置
            dspy.configure(lm=self._lm_instance)
            
            # 保存設置
            self._settings = {
                'dspy_config': dspy_config,
                'model_config': model_config,
                'initialized_at': dspy.settings.current_time() if hasattr(dspy.settings, 'current_time') else 'unknown'
            }
            
            self._is_initialized = True
            logger.info("DSPy 環境初始化成功")
            
            return True
            
        except Exception as e:
            logger.error(f"DSPy 初始化失敗: {e}", exc_info=True)
            self._cleanup()
            return False
    
    def is_initialized(self) -> bool:
        """檢查是否已初始化
        
        Returns:
            是否已初始化
        """
        return self._is_initialized
    
    def get_lm(self) -> Optional[DSPyGeminiLM]:
        """獲取 Language Model 實例
        
        Returns:
            DSPyGeminiLM 實例或 None
        """
        return self._lm_instance
    
    def get_settings(self) -> Optional[Dict[str, Any]]:
        """獲取當前設置
        
        Returns:
            設置字典或 None
        """
        return self._settings.copy() if self._settings else None
    
    def reinitialize(self, config_override: Optional[Dict[str, Any]] = None) -> bool:
        """重新初始化 DSPy 環境
        
        Args:
            config_override: 配置覆寫
            
        Returns:
            是否重新初始化成功
        """
        logger.info("重新初始化 DSPy 環境...")
        self.cleanup()
        return self.initialize(config_override)
    
    def cleanup(self):
        """清理 DSPy 環境"""
        logger.info("清理 DSPy 環境...")
        self._cleanup()
    
    def _cleanup(self):
        """內部清理方法"""
        if self._lm_instance:
            # 重置統計信息
            if hasattr(self._lm_instance, 'reset_stats'):
                self._lm_instance.reset_stats()
            self._lm_instance = None
        
        self._settings = None
        self._is_initialized = False
        
        # 重置 DSPy 全局配置（如果可能）
        try:
            dspy.configure(lm=None)
        except:
            pass  # 忽略清理錯誤
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計信息
        
        Returns:
            統計信息字典
        """
        stats = {
            "initialized": self._is_initialized,
            "lm_stats": None
        }
        
        if self._lm_instance:
            stats["lm_stats"] = self._lm_instance.get_stats()
        
        return stats

# 全局 DSPy 管理器實例
_global_manager: Optional[DSPyManager] = None

def get_dspy_manager() -> DSPyManager:
    """獲取全局 DSPy 管理器實例
    
    Returns:
        DSPyManager 實例
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = DSPyManager()
    return _global_manager

def initialize_dspy(config_override: Optional[Dict[str, Any]] = None) -> bool:
    """初始化全局 DSPy 環境
    
    Args:
        config_override: 配置覆寫
        
    Returns:
        是否初始化成功
    """
    manager = get_dspy_manager()
    return manager.initialize(config_override)

def is_dspy_initialized() -> bool:
    """檢查 DSPy 是否已初始化
    
    Returns:
        是否已初始化
    """
    manager = get_dspy_manager()
    return manager.is_initialized()

def get_dspy_lm() -> Optional[DSPyGeminiLM]:
    """獲取全局 DSPy Language Model 實例
    
    Returns:
        DSPyGeminiLM 實例或 None
    """
    manager = get_dspy_manager()
    return manager.get_lm()

def reinitialize_dspy(config_override: Optional[Dict[str, Any]] = None) -> bool:
    """重新初始化全局 DSPy 環境
    
    Args:
        config_override: 配置覆寫
        
    Returns:
        是否重新初始化成功
    """
    manager = get_dspy_manager()
    return manager.reinitialize(config_override)

def cleanup_dspy():
    """清理全局 DSPy 環境"""
    manager = get_dspy_manager()
    manager.cleanup()

def get_dspy_stats() -> Dict[str, Any]:
    """獲取 DSPy 統計信息
    
    Returns:
        統計信息字典
    """
    manager = get_dspy_manager()
    return manager.get_stats()

# 上下文管理器
class DSPyContext:
    """DSPy 上下文管理器
    
    用於在 with 語句中管理 DSPy 環境。
    """
    
    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.config_override = config_override
        self.was_initialized = False
    
    def __enter__(self) -> DSPyManager:
        """進入上下文"""
        manager = get_dspy_manager()
        
        # 記錄原始狀態
        self.was_initialized = manager.is_initialized()
        
        # 如果尚未初始化，則初始化
        if not self.was_initialized:
            if not manager.initialize(self.config_override):
                raise RuntimeError("DSPy 初始化失敗")
        
        return manager
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        # 如果原本未初始化，則清理
        if not self.was_initialized:
            cleanup_dspy()

# 便捷函數
def with_dspy(config_override: Optional[Dict[str, Any]] = None):
    """DSPy 上下文管理器便捷函數
    
    Args:
        config_override: 配置覆寫
        
    Returns:
        DSPyContext 實例
        
    Example:
        with with_dspy() as manager:
            lm = manager.get_lm()
            # 使用 DSPy...
    """
    return DSPyContext(config_override)

def ensure_dspy_initialized(config_override: Optional[Dict[str, Any]] = None) -> bool:
    """確保 DSPy 已初始化
    
    如果尚未初始化，則進行初始化。
    
    Args:
        config_override: 配置覆寫
        
    Returns:
        是否初始化成功
    """
    if is_dspy_initialized():
        return True
    
    return initialize_dspy(config_override)

# 測試函數
def test_dspy_setup():
    """測試 DSPy 設置"""
    logger.info("測試 DSPy 設置...")
    
    try:
        # 測試初始化
        success = initialize_dspy()
        if not success:
            logger.error("DSPy 初始化失敗")
            return False
        
        # 測試狀態檢查
        if not is_dspy_initialized():
            logger.error("DSPy 初始化狀態檢查失敗")
            return False
        
        # 測試獲取 LM
        lm = get_dspy_lm()
        if lm is None:
            logger.error("無法獲取 DSPy LM 實例")
            return False
        
        # 測試統計信息
        stats = get_dspy_stats()
        logger.info(f"DSPy 統計信息: {stats}")
        
        # 測試清理
        cleanup_dspy()
        
        if is_dspy_initialized():
            logger.error("DSPy 清理後仍然顯示已初始化")
            return False
        
        logger.info("DSPy 設置測試成功")
        return True
        
    except Exception as e:
        logger.error(f"DSPy 設置測試失敗: {e}")
        return False

if __name__ == "__main__":
    # 設置日誌
    logging.basicConfig(level=logging.INFO)
    
    # 運行測試
    test_dspy_setup()
