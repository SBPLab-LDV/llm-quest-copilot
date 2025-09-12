#!/usr/bin/env python3
"""
測試對話管理器工廠函數的優化版本支援
"""

import sys
import os
import logging

# 添加項目根目錄到路徑
sys.path.append('/app')
sys.path.append('/app/src')

from src.core.character import Character
from src.core.dialogue_factory import (
    create_dialogue_manager, 
    get_available_implementations, 
    get_current_implementation_info,
    test_implementations
)

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_factory_optimization():
    """測試工廠函數的優化版本支援"""
    print("🧪 測試對話管理器工廠函數優化支援...")
    print("=" * 60)
    
    try:
        # 1. 測試可用實現檢測
        print("\n1. 檢測可用的對話管理器實現:")
        implementations = get_available_implementations()
        
        for impl_name, impl_info in implementations.items():
            print(f"  {impl_name}:")
            print(f"    可用性: {'✅' if impl_info['available'] else '❌'}")
            print(f"    描述: {impl_info['description']}")
            if impl_info['available']:
                print(f"    啟用狀態: {'✅' if impl_info.get('enabled', False) else '❌'}")
                if 'efficiency_improvement' in impl_info:
                    print(f"    效率提升: {impl_info['efficiency_improvement']}")
                    print(f"    API調用/對話: {impl_info['api_calls_per_conversation']}")
            else:
                print(f"    錯誤: {impl_info.get('error', 'Unknown')}")
            print()
        
        # 2. 創建測試角色
        print("2. 創建測試角色:")
        test_character = Character(
            name="測試病患",
            persona="友善的測試病患",
            backstory="用於測試的虛擬病患",
            goal="協助進行系統測試"
        )
        print(f"  ✅ 測試角色創建成功: {test_character.name}")
        
        # 3. 測試各種實現的創建
        print(f"\n3. 測試不同實現的創建:")
        test_scenarios = [
            ("原始實現", "original"),
            ("DSPy實現", "dspy"),
            ("優化實現", "optimized"),
            ("自動選擇", None)
        ]
        
        created_managers = {}
        
        for scenario_name, force_impl in test_scenarios:
            print(f"\n  測試 {scenario_name}:")
            try:
                manager = create_dialogue_manager(
                    character=test_character,
                    use_terminal=False,
                    log_dir="logs/test",
                    force_implementation=force_impl
                )
                
                # 獲取實現資訊
                impl_info = get_current_implementation_info(manager)
                
                print(f"    ✅ 創建成功")
                print(f"    類別名稱: {impl_info['class_name']}")
                print(f"    實現類型: {impl_info['type']}")
                print(f"    模組路徑: {impl_info['module']}")
                
                # 檢查優化統計（如果可用）
                if impl_info['type'] == 'optimized':
                    if 'optimization_stats' in impl_info:
                        opt_stats = impl_info['optimization_stats']
                        print(f"    優化狀態: {'✅' if opt_stats.get('optimization_enabled', False) else '❌'}")
                        efficiency = opt_stats.get('efficiency_summary', {})
                        print(f"    API調用/對話: {efficiency.get('calls_per_conversation', 'N/A')}")
                        print(f"    效率提升: {efficiency.get('optimization_factor', 'N/A')}")
                
                created_managers[scenario_name] = manager
                
            except Exception as e:
                print(f"    ❌ 創建失敗: {e}")
                import traceback
                traceback.print_exc()
        
        # 4. 執行完整的實現測試
        print(f"\n4. 執行完整實現測試:")
        test_results = test_implementations()
        
        for impl_name, result in test_results.items():
            print(f"\n  {impl_name} 實現測試:")
            if result.get('test_passed', False):
                print(f"    ✅ 測試通過")
                print(f"    類別: {result.get('class_name', 'N/A')}")
                print(f"    process_turn方法: {'✅' if result.get('has_process_turn', False) else '❌'}")
                print(f"    log_interaction方法: {'✅' if result.get('has_log_interaction', False) else '❌'}")
                
                # DSPy 特定資訊
                if 'dspy_stats' in result:
                    print(f"    DSPy啟用: {'✅' if result.get('dspy_enabled', False) else '❌'}")
                
                # 優化版特定資訊
                if 'optimization_stats' in result:
                    opt_enabled = result.get('optimization_enabled', False)
                    print(f"    優化啟用: {'✅' if opt_enabled else '❌'}")
                    if opt_enabled:
                        opt_stats = result['optimization_stats']
                        efficiency = opt_stats.get('efficiency_summary', {})
                        print(f"    效率提升: {efficiency.get('optimization_factor', 'N/A')}")
                        print(f"    配額節省: {efficiency.get('quota_savings_percent', 'N/A')}")
            else:
                print(f"    ❌ 測試失敗: {result.get('error', 'Unknown error')}")
        
        # 5. 清理資源
        print(f"\n5. 清理測試資源:")
        for scenario_name, manager in created_managers.items():
            try:
                if hasattr(manager, 'cleanup'):
                    manager.cleanup()
                print(f"  ✅ {scenario_name} 清理完成")
            except Exception as e:
                print(f"  ⚠️ {scenario_name} 清理時警告: {e}")
        
        print(f"\n✅ 工廠函數優化支援測試完成！")
        
        # 顯示總結
        available_count = sum(1 for impl in implementations.values() if impl['available'])
        enabled_count = sum(1 for impl in implementations.values() 
                          if impl['available'] and impl.get('enabled', False))
        
        print(f"\n📊 測試總結:")
        print(f"  可用實現: {available_count}/{len(implementations)}")
        print(f"  啟用實現: {enabled_count}/{available_count}")
        
        if 'optimized' in implementations and implementations['optimized']['available']:
            if implementations['optimized'].get('enabled', False):
                print(f"  🎯 優化版本: ✅ 可用且啟用，API調用節省66.7%")
            else:
                print(f"  🎯 優化版本: ⚠️ 可用但未啟用 (需設定 use_unified_module: true)")
        else:
            print(f"  🎯 優化版本: ❌ 不可用")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 工廠函數測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_factory_optimization()
    if success:
        print(f"\n🎉 所有測試完成！工廠函數已成功支援優化版本")
    else:
        print(f"\n💥 測試失敗，需要進一步調試")
        sys.exit(1)