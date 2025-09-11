#!/usr/bin/env python3
"""
DSPy 配置模組的測試

測試 DSPy 配置管理功能是否正常運作。
"""

import sys
import os
import tempfile
import yaml

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, '/app')

def test_config_loading():
    """測試配置載入功能"""
    print("🧪 測試 DSPy 配置載入...")
    
    try:
        from src.core.dspy.config import DSPyConfig, get_config
        
        # 測試全局配置實例
        config = get_config()
        assert config is not None, "無法獲取配置實例"
        
        # 測試配置載入
        full_config = config.load_config()
        assert isinstance(full_config, dict), "配置應該是字典類型"
        
        # 測試 DSPy 配置
        dspy_config = config.get_dspy_config()
        assert isinstance(dspy_config, dict), "DSPy 配置應該是字典類型"
        assert 'enabled' in dspy_config, "DSPy 配置應包含 enabled 欄位"
        
        print("✅ 配置載入測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 配置載入測試失敗: {e}")
        return False

def test_config_methods():
    """測試配置方法"""
    print("🧪 測試 DSPy 配置方法...")
    
    try:
        from src.core.dspy.config import get_config
        
        config = get_config()
        
        # 測試各種配置方法
        is_enabled = config.is_dspy_enabled()
        assert isinstance(is_enabled, bool), "is_dspy_enabled 應返回布爾值"
        
        is_optimized = config.is_optimization_enabled()
        assert isinstance(is_optimized, bool), "is_optimization_enabled 應返回布爾值"
        
        model_config = config.get_model_config()
        assert isinstance(model_config, dict), "model_config 應該是字典類型"
        assert 'model' in model_config, "model_config 應包含 model 欄位"
        
        ab_config = config.get_ab_testing_config()
        assert isinstance(ab_config, dict), "ab_testing_config 應該是字典類型"
        
        cache_config = config.get_caching_config()
        assert isinstance(cache_config, dict), "caching_config 應該是字典類型"
        
        api_key = config.get_google_api_key()
        assert isinstance(api_key, str), "Google API Key 應該是字符串"
        
        print("✅ 配置方法測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 配置方法測試失敗: {e}")
        return False

def test_config_with_custom_file():
    """測試使用自定義配置文件"""
    print("🧪 測試自定義配置文件...")
    
    try:
        from src.core.dspy.config import DSPyConfig
        
        # 創建臨時配置文件
        test_config = {
            'google_api_key': 'test_key',
            'dspy': {
                'enabled': True,
                'optimize': True,
                'model': 'test-model'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_config_path = f.name
        
        try:
            # 使用自定義配置創建實例
            config = DSPyConfig(temp_config_path)
            
            # 測試配置值
            assert config.is_dspy_enabled() == True, "DSPy 應該被啟用"
            assert config.is_optimization_enabled() == True, "優化應該被啟用"
            
            model_config = config.get_model_config()
            assert model_config['model'] == 'test-model', "模型名稱應該是 test-model"
            
            api_key = config.get_google_api_key()
            assert api_key == 'test_key', "API Key 應該是 test_key"
            
            print("✅ 自定義配置文件測試通過")
            return True
            
        finally:
            # 清理臨時文件
            os.unlink(temp_config_path)
        
    except Exception as e:
        print(f"❌ 自定義配置文件測試失敗: {e}")
        return False

def run_all_tests():
    """運行所有配置測試"""
    print("🚀 開始 DSPy 配置測試...")
    print("=" * 50)
    
    tests = [
        test_config_loading,
        test_config_methods,
        test_config_with_custom_file
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 測試 {test_func.__name__} 出現未預期錯誤: {e}")
        print()
    
    print("=" * 50)
    print(f"📊 測試結果: {passed}/{total} 通過")
    
    if passed == total:
        print("🎉 所有配置測試都通過了！")
        return True
    else:
        print("⚠️ 部分測試失敗，請檢查上述錯誤訊息")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)