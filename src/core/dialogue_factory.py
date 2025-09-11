#!/usr/bin/env python3
"""
對話管理器工廠模式

根據配置創建適當的對話管理器實現，支援原始版本和 DSPy 版本的切換。
"""

import logging
from typing import Optional, Type, Dict, Any

from .character import Character
from .dialogue import DialogueManager


def create_dialogue_manager(character: Character, 
                           use_terminal: bool = False, 
                           log_dir: str = "logs",
                           force_implementation: Optional[str] = None) -> DialogueManager:
    """根據配置創建對話管理器
    
    Args:
        character: 角色實例
        use_terminal: 是否使用終端模式
        log_dir: 日誌目錄
        force_implementation: 強制使用特定實現 ("original", "dspy", None=auto)
        
    Returns:
        DialogueManager 實例（原始版本或 DSPy 版本）
        
    Raises:
        ImportError: 當請求的實現無法導入時
        ValueError: 當 force_implementation 參數無效時
    """
    logger = logging.getLogger(__name__)
    
    # 記錄工廠函數調用
    logger.info(f"Creating dialogue manager: character={character.name}, "
                f"terminal={use_terminal}, force={force_implementation}")
    
    # 根據強制參數決定實現
    if force_implementation:
        if force_implementation.lower() == "original":
            logger.info("Forced to use original DialogueManager")
            return _create_original_manager(character, use_terminal, log_dir)
        elif force_implementation.lower() == "dspy":
            logger.info("Forced to use DSPy DialogueManager")
            return _create_dspy_manager(character, use_terminal, log_dir)
        else:
            raise ValueError(f"Invalid force_implementation: {force_implementation}")
    
    # 自動選擇實現
    try:
        # 首先嘗試讀取配置
        from .dspy.config import DSPyConfig
        
        config = DSPyConfig()
        if config.is_dspy_enabled():
            logger.info("DSPy enabled in config - creating DSPy DialogueManager")
            return _create_dspy_manager(character, use_terminal, log_dir)
        else:
            logger.info("DSPy disabled in config - creating original DialogueManager")
            return _create_original_manager(character, use_terminal, log_dir)
            
    except ImportError as e:
        logger.warning(f"Failed to load DSPy config: {e}")
        logger.info("Falling back to original DialogueManager")
        return _create_original_manager(character, use_terminal, log_dir)
    
    except Exception as e:
        logger.error(f"Unexpected error in dialogue manager factory: {e}")
        logger.info("Falling back to original DialogueManager")
        return _create_original_manager(character, use_terminal, log_dir)


def _create_original_manager(character: Character, 
                           use_terminal: bool, 
                           log_dir: str) -> DialogueManager:
    """創建原始對話管理器"""
    logger = logging.getLogger(__name__)
    
    try:
        manager = DialogueManager(character, use_terminal, log_dir)
        logger.debug(f"Original DialogueManager created successfully")
        return manager
        
    except Exception as e:
        logger.error(f"Failed to create original DialogueManager: {e}")
        raise


def _create_dspy_manager(character: Character, 
                        use_terminal: bool, 
                        log_dir: str) -> DialogueManager:
    """創建 DSPy 對話管理器"""
    logger = logging.getLogger(__name__)
    
    try:
        from .dspy.dialogue_manager_dspy import DialogueManagerDSPy
        
        manager = DialogueManagerDSPy(character, use_terminal, log_dir)
        logger.debug(f"DSPy DialogueManager created successfully")
        return manager
        
    except ImportError as e:
        logger.error(f"Failed to import DSPy DialogueManager: {e}")
        logger.warning("Falling back to original DialogueManager")
        return _create_original_manager(character, use_terminal, log_dir)
        
    except Exception as e:
        logger.error(f"Failed to create DSPy DialogueManager: {e}")
        logger.warning("Falling back to original DialogueManager")
        return _create_original_manager(character, use_terminal, log_dir)


def get_available_implementations() -> Dict[str, Dict[str, Any]]:
    """獲取可用的對話管理器實現資訊
    
    Returns:
        實現名稱到實現資訊的映射
    """
    logger = logging.getLogger(__name__)
    implementations = {}
    
    # 檢查原始實現
    try:
        from .dialogue import DialogueManager
        implementations["original"] = {
            "available": True,
            "class": DialogueManager,
            "description": "原始對話管理器實現"
        }
    except ImportError as e:
        implementations["original"] = {
            "available": False,
            "error": str(e),
            "description": "原始對話管理器實現"
        }
    
    # 檢查 DSPy 實現
    try:
        from .dspy.dialogue_manager_dspy import DialogueManagerDSPy
        from .dspy.config import DSPyConfig
        
        config = DSPyConfig()
        implementations["dspy"] = {
            "available": True,
            "class": DialogueManagerDSPy,
            "enabled": config.is_dspy_enabled(),
            "description": "DSPy 框架對話管理器實現"
        }
    except ImportError as e:
        implementations["dspy"] = {
            "available": False,
            "error": str(e),
            "description": "DSPy 框架對話管理器實現"
        }
    
    logger.debug(f"Available implementations: {list(implementations.keys())}")
    return implementations


def get_current_implementation_info(manager: DialogueManager) -> Dict[str, Any]:
    """獲取對話管理器實例的實現資訊
    
    Args:
        manager: 對話管理器實例
        
    Returns:
        實現資訊字典
    """
    info = {
        "class_name": manager.__class__.__name__,
        "module": manager.__class__.__module__,
        "type": "unknown"
    }
    
    # 判斷實現類型
    if manager.__class__.__name__ == "DialogueManager":
        info["type"] = "original"
    elif manager.__class__.__name__ == "DialogueManagerDSPy":
        info["type"] = "dspy"
        
        # 獲取 DSPy 特定資訊
        if hasattr(manager, 'get_dspy_statistics'):
            try:
                info["dspy_stats"] = manager.get_dspy_statistics()
            except Exception as e:
                info["dspy_stats_error"] = str(e)
    
    return info


def test_implementations() -> Dict[str, Dict[str, Any]]:
    """測試所有可用實現的基本功能
    
    Returns:
        實現名稱到測試結果的映射
    """
    logger = logging.getLogger(__name__)
    results = {}
    
    # 創建測試角色
    try:
        from .character import Character
        test_character = Character(
            name="測試角色",
            persona="友善的測試角色",
            backstory="用於測試的虛擬角色",
            goal="協助進行系統測試"
        )
    except Exception as e:
        logger.error(f"Failed to create test character: {e}")
        return {"error": f"無法創建測試角色: {e}"}
    
    implementations = get_available_implementations()
    
    for impl_name, impl_info in implementations.items():
        if not impl_info["available"]:
            results[impl_name] = {
                "test_passed": False,
                "error": f"Implementation not available: {impl_info.get('error', 'Unknown error')}"
            }
            continue
            
        try:
            # 嘗試創建實例
            manager = create_dialogue_manager(
                character=test_character,
                force_implementation=impl_name
            )
            
            # 基本功能測試
            test_result = {
                "test_passed": True,
                "creation_success": True,
                "class_name": manager.__class__.__name__,
                "has_process_turn": hasattr(manager, 'process_turn'),
                "has_log_interaction": hasattr(manager, 'log_interaction')
            }
            
            # DSPy 特定測試
            if impl_name == "dspy" and hasattr(manager, 'get_dspy_statistics'):
                stats = manager.get_dspy_statistics()
                test_result["dspy_stats"] = stats
                test_result["dspy_enabled"] = getattr(manager, 'dspy_enabled', False)
            
            # 清理
            if hasattr(manager, 'cleanup'):
                manager.cleanup()
                
            results[impl_name] = test_result
            logger.info(f"{impl_name} implementation test passed")
            
        except Exception as e:
            results[impl_name] = {
                "test_passed": False,
                "error": str(e)
            }
            logger.error(f"{impl_name} implementation test failed: {e}")
    
    return results


# 向後兼容的別名
DialogueManagerFactory = create_dialogue_manager