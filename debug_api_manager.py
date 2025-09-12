#!/usr/bin/env python3
"""
調試 API 服務器的對話管理器實現版本檢測
"""

import sys
import os
import logging

# 添加項目根目錄到路徑
sys.path.append('/app')
sys.path.append('/app/src')

from src.core.character import Character
from src.api.server import create_dialogue_manager_with_monitoring

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def debug_api_manager():
    """調試 API 服務器的對話管理器檢測"""
    print("🔍 調試 API 服務器的對話管理器實現版本檢測...")
    print("=" * 60)
    
    try:
        # 創建測試角色
        test_character = Character(
            name="測試病患",
            persona="友善的測試病患", 
            backstory="用於調試的虛擬病患",
            goal="協助進行系統調試"
        )
        print(f"✅ 測試角色創建成功: {test_character.name}")
        
        # 使用 API 服務器的管理器創建函數
        print(f"\n🔍 使用 API 服務器創建對話管理器...")
        manager, implementation_version = create_dialogue_manager_with_monitoring(
            character=test_character,
            log_dir="logs/debug"
        )
        
        print(f"✅ 對話管理器創建成功")
        print(f"  類別名稱: {manager.__class__.__name__}")
        print(f"  實現版本: {implementation_version}")
        print(f"  模組路徑: {manager.__class__.__module__}")
        
        # 詳細檢查屬性
        print(f"\n🔍 詳細屬性檢查:")
        attrs_to_check = [
            'optimization_enabled',
            'dspy_enabled', 
            'get_optimization_statistics',
            'get_dspy_statistics',
            'process_turn'
        ]
        
        for attr in attrs_to_check:
            has_attr = hasattr(manager, attr)
            print(f"  {attr}: {'✅' if has_attr else '❌'}")
            if has_attr and attr.startswith('get_'):
                try:
                    # 嘗試調用getter方法
                    result = getattr(manager, attr)()
                    print(f"    -> {attr}(): {type(result).__name__} with {len(result) if isinstance(result, (dict, list)) else 'N/A'} items")
                except Exception as e:
                    print(f"    -> {attr}(): ERROR - {e}")
            elif has_attr:
                try:
                    value = getattr(manager, attr)
                    print(f"    -> {attr}: {value}")
                except Exception as e:
                    print(f"    -> {attr}: ERROR - {e}")
        
        # 檢測邏輯重現
        print(f"\n🔍 重現 API 服務器的檢測邏輯:")
        detected_version = "original"
        if hasattr(manager, 'optimization_enabled') and manager.optimization_enabled:
            detected_version = "optimized"
            print(f"  ✅ 檢測到優化版本")
        elif hasattr(manager, 'dspy_enabled') and manager.dspy_enabled:
            detected_version = "dspy"
            print(f"  ✅ 檢測到 DSPy 版本")
        else:
            print(f"  ✅ 檢測到原始版本")
        
        print(f"  最終檢測結果: {detected_version}")
        
        if detected_version != implementation_version:
            print(f"  ⚠️ 檢測邏輯不一致！")
            print(f"    create_dialogue_manager_with_monitoring 返回: {implementation_version}")
            print(f"    重現檢測邏輯得出: {detected_version}")
        else:
            print(f"  ✅ 檢測邏輯一致")
        
        # 清理
        if hasattr(manager, 'cleanup'):
            manager.cleanup()
            print(f"\n✅ 管理器清理完成")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 調試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_api_manager()
    if success:
        print(f"\n🎉 調試完成！")
    else:
        print(f"\n💥 調試失敗")
        sys.exit(1)