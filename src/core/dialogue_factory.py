#!/usr/bin/env python3
"""
對話管理器工廠模式

本專案已全面採用 DSPy optimized 實作（Unified module）。
因此只允許建立 `OptimizedDialogueManagerDSPy`，任何初始化失敗皆 fail-fast。
"""

import logging
from typing import Optional, Dict, Any

from .character import Character
from .dialogue import DialogueManager


def create_dialogue_manager(character: Character, 
                           use_terminal: bool = False, 
                           log_dir: str = "logs",
                           force_implementation: Optional[str] = None,
                           log_file_basename: Optional[str] = None) -> DialogueManager:
    """根據配置創建對話管理器
    
    Args:
        character: 角色實例
        use_terminal: 是否使用終端模式
        log_dir: 日誌目錄
        force_implementation: 強制使用特定實現（僅支援 "optimized"；None=auto）
        
    Returns:
        OptimizedDialogueManagerDSPy 實例
        
    Raises:
        ImportError: 當請求的實現無法導入時
        ValueError: 當 force_implementation 參數無效時
    """
    logger = logging.getLogger(__name__)
    
    # 記錄工廠函數調用
    logger.info(f"Creating dialogue manager: character={character.name}, "
                f"terminal={use_terminal}, force={force_implementation}")
    
    if force_implementation and force_implementation.lower() != "optimized":
        raise ValueError(f"Invalid force_implementation: {force_implementation} (only 'optimized' is supported)")

    logger.info("Creating Optimized DSPy DialogueManager (fail-fast)")
    return _create_optimized_dspy_manager(character, use_terminal, log_dir, log_file_basename)


def _create_optimized_dspy_manager(character: Character, 
                                  use_terminal: bool, 
                                  log_dir: str,
                                  log_file_basename: Optional[str] = None) -> DialogueManager:
    """創建優化版 DSPy 對話管理器（統一模組，節省 66.7% API 調用）"""
    logger = logging.getLogger(__name__)
    
    from .dspy.optimized_dialogue_manager import OptimizedDialogueManagerDSPy

    manager = OptimizedDialogueManagerDSPy(character, use_terminal, log_dir, log_file_basename=log_file_basename)
    logger.debug("Optimized DSPy DialogueManager created successfully")
    return manager


def get_available_implementations() -> Dict[str, Dict[str, Any]]:
    """獲取可用的對話管理器實現資訊
    
    Returns:
        實現名稱到實現資訊的映射
    """
    logger = logging.getLogger(__name__)
    implementations: Dict[str, Dict[str, Any]] = {}

    try:
        from .dspy.optimized_dialogue_manager import OptimizedDialogueManagerDSPy
        implementations["optimized"] = {
            "available": True,
            "class": OptimizedDialogueManagerDSPy,
            "enabled": True,
            "description": "優化版 DSPy 對話管理器（統一模組，節省 66.7% API 調用）",
            "api_calls_per_conversation": 1,
            "efficiency_improvement": "66.7%",
        }
    except ImportError as e:
        implementations["optimized"] = {
            "available": False,
            "error": str(e),
            "description": "優化版 DSPy 對話管理器（統一模組，節省 66.7% API 調用）",
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
    if manager.__class__.__name__ == "OptimizedDialogueManagerDSPy":
        info["type"] = "optimized"
        
        # 獲取優化版特定資訊
        if hasattr(manager, 'get_optimization_statistics'):
            try:
                info["optimization_stats"] = manager.get_optimization_statistics()
            except Exception as e:
                info["optimization_stats_error"] = str(e)
    
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
    
    impl_name = "optimized"
    impl_info = get_available_implementations().get(impl_name) or {}
    if not impl_info.get("available"):
        return {
            impl_name: {
                "test_passed": False,
                "error": f"Implementation not available: {impl_info.get('error', 'Unknown error')}",
            }
        }

    manager = create_dialogue_manager(character=test_character, force_implementation="optimized")
    test_result = {
        "test_passed": True,
        "creation_success": True,
        "class_name": manager.__class__.__name__,
        "has_process_turn": hasattr(manager, 'process_turn'),
        "has_log_interaction": hasattr(manager, 'log_interaction'),
    }
    if hasattr(manager, 'get_optimization_statistics'):
        try:
            test_result["optimization_stats"] = manager.get_optimization_statistics()
        except Exception as e:
            test_result["optimization_stats_error"] = str(e)
    if hasattr(manager, 'cleanup'):
        manager.cleanup()
    results[impl_name] = test_result
    
    return results


# 向後兼容的別名
DialogueManagerFactory = create_dialogue_manager
