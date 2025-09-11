#!/usr/bin/env python3
"""
簡單的 DSPy Signature 測試

測試 DSPy Signature 的正確定義方式。
"""

import sys
sys.path.insert(0, '/app')

def test_simple_signature():
    """測試簡單的 DSPy Signature"""
    print("🧪 測試簡單的 DSPy Signature...")
    
    try:
        import dspy
        
        # 創建一個簡單的簽名來測試語法
        class SimpleTestSignature(dspy.Signature):
            """簡單測試簽名"""
            input_text = dspy.InputField(desc="輸入文本")
            output_text = dspy.OutputField(desc="輸出文本")
        
        print("✅ 簡單簽名創建成功")
        
        # 檢查欄位
        print(f"  簽名類型: {type(SimpleTestSignature)}")
        print(f"  是否有 input_text: {hasattr(SimpleTestSignature, 'input_text')}")
        print(f"  是否有 output_text: {hasattr(SimpleTestSignature, 'output_text')}")
        
        if hasattr(SimpleTestSignature, 'input_text'):
            input_field = getattr(SimpleTestSignature, 'input_text')
            print(f"  input_text 類型: {type(input_field)}")
            print(f"  是 InputField: {isinstance(input_field, dspy.InputField)}")
        
        if hasattr(SimpleTestSignature, 'output_text'):
            output_field = getattr(SimpleTestSignature, 'output_text')
            print(f"  output_text 類型: {type(output_field)}")
            print(f"  是 OutputField: {isinstance(output_field, dspy.OutputField)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 簡單簽名測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_our_signature():
    """測試我們的患者回應簽名"""
    print("🧪 測試我們的患者回應簽名...")
    
    try:
        from src.core.dspy.signatures import PatientResponseSignature
        
        print(f"  簽名類型: {type(PatientResponseSignature)}")
        print(f"  是否有 user_input: {hasattr(PatientResponseSignature, 'user_input')}")
        print(f"  是否有 responses: {hasattr(PatientResponseSignature, 'responses')}")
        
        # 檢查所有屬性
        attrs = [attr for attr in dir(PatientResponseSignature) if not attr.startswith('_')]
        print(f"  所有公共屬性: {attrs}")
        
        if hasattr(PatientResponseSignature, 'user_input'):
            field = getattr(PatientResponseSignature, 'user_input')
            print(f"  user_input 類型: {type(field)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 患者回應簽名測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 開始簡單的 DSPy Signature 測試...")
    print("=" * 50)
    
    success1 = test_simple_signature()
    print()
    success2 = test_our_signature()
    
    print("=" * 50)
    if success1 and success2:
        print("🎉 測試完成")
    else:
        print("⚠️ 部分測試失敗")