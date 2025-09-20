#!/usr/bin/env python3
"""
檢查 DSPy 3.0 的正確用法
"""

import sys
sys.path.insert(0, '/app')

def check_dspy_structure():
    """檢查 DSPy 結構"""
    print("🔍 檢查 DSPy 結構...")
    
    try:
        import dspy
        print(f"DSPy 版本: {dspy.__version__}")
        
        # 檢查 Signature 相關
        signature_items = [x for x in dir(dspy) if 'signature' in x.lower()]
        print(f"Signature 相關項目: {signature_items}")
        
        # 檢查 Field 相關
        field_items = [x for x in dir(dspy) if 'field' in x.lower()]
        print(f"Field 相關項目: {field_items}")
        
        # 嘗試創建簽名
        print("\n嘗試不同的簽名創建方式:")
        
        # 方式 1: 傳統方式
        try:
            class TestSig1(dspy.Signature):
                """Test signature 1"""
                input_text = dspy.InputField(desc="Input")
                output_text = dspy.OutputField(desc="Output")
            
            print("✅ 方式 1 成功: 傳統 class 定義")
            print(f"  欄位: {list(TestSig1.__fields__.keys()) if hasattr(TestSig1, '__fields__') else 'no __fields__'}")
            
        except Exception as e:
            print(f"❌ 方式 1 失敗: {e}")
        
        # 方式 2: 字符串形式
        try:
            sig2 = dspy.Signature("input_text -> output_text")
            print("✅ 方式 2 成功: 字符串定義")
            print(f"  類型: {type(sig2)}")
            
        except Exception as e:
            print(f"❌ 方式 2 失敗: {e}")
        
        # 方式 3: 檢查 dspy 模組的其他內容
        print(f"\nDSPy 全部內容 (前 20 個):")
        all_items = [x for x in dir(dspy) if not x.startswith('_')][:20]
        for item in all_items:
            print(f"  {item}")
        
        return True
        
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_dspy_structure()