#!/usr/bin/env python3
"""
測試 DSPy 範例加載器的調試版本
"""

import sys
sys.path.insert(0, '/app')

def debug_yaml_structure():
    """調試 YAML 結構"""
    print("🔍 調試 YAML 結構...")
    
    import yaml
    from pathlib import Path
    
    # 檢查一個具體的檔案
    yaml_file = Path("/app/prompts/context_examples/vital_signs_examples.yaml")
    
    if yaml_file.exists():
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        print(f"檔案內容結構:")
        print(f"  主要鍵值: {list(data.keys())}")
        
        for key, value in data.items():
            print(f"  {key}: {type(value)}")
            if isinstance(value, dict):
                print(f"    子鍵值: {list(value.keys())}")
            elif isinstance(value, list) and len(value) > 0:
                print(f"    第一個元素類型: {type(value[0])}")
                if isinstance(value[0], dict):
                    print(f"    第一個元素鍵值: {list(value[0].keys())}")
    else:
        print(f"檔案不存在: {yaml_file}")

def test_example_loading():
    """測試範例加載"""
    print("🧪 測試範例加載...")
    
    try:
        from src.core.dspy.example_loader import ExampleLoader
        
        # 創建加載器
        loader = ExampleLoader()
        
        # 手動測試 YAML 加載
        yaml_file = "/app/prompts/context_examples/vital_signs_examples.yaml"
        yaml_data = loader.load_yaml_file(yaml_file)
        
        print(f"YAML 資料: {yaml_data}")
        
        # 嘗試轉換
        examples = loader.yaml_to_dspy_examples(yaml_data, "vital_signs_examples")
        print(f"轉換結果: {len(examples)} 個範例")
        
        if examples:
            example = examples[0]
            print(f"第一個範例:")
            print(f"  user_input: {getattr(example, 'user_input', 'N/A')}")
            print(f"  responses: {getattr(example, 'responses', 'N/A')}")
            
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_yaml_structure()
    print()
    test_example_loading()