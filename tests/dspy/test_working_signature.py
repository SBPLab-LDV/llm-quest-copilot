#!/usr/bin/env python3
"""
測試工作的 DSPy Signatures
"""

import sys
sys.path.insert(0, '/app')

def test_working_signature():
    """測試工作的簽名"""
    print("🧪 測試工作的 DSPy Signatures...")
    
    try:
        import dspy
        
        # 創建工作的簽名
        class WorkingSignature(dspy.Signature):
            """工作的簽名"""
            input_text = dspy.InputField(desc="輸入文本")
            output_text = dspy.OutputField(desc="輸出文本")
        
        print("✅ 簽名創建成功")
        
        # 檢查欄位（使用正確的方式）
        print(f"model_fields: {list(WorkingSignature.model_fields.keys())}")
        
        # 檢查每個欄位
        for field_name, field_info in WorkingSignature.model_fields.items():
            print(f"  {field_name}: {field_info}")
        
        # 測試我們的 PatientResponseSignature
        print("\n測試 PatientResponseSignature:")
        from src.core.dspy.signatures import PatientResponseSignature
        
        if hasattr(PatientResponseSignature, 'model_fields'):
            print(f"PatientResponseSignature 欄位: {list(PatientResponseSignature.model_fields.keys())}")
            
            # 檢查是否有預期的欄位
            expected_fields = ['user_input', 'character_name', 'responses', 'state', 'dialogue_context']
            for field in expected_fields:
                if field in PatientResponseSignature.model_fields:
                    print(f"  ✓ {field}")
                else:
                    print(f"  ❌ 缺少 {field}")
        else:
            print("PatientResponseSignature 沒有 model_fields")
        
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_signature_creation():
    """測試簽名創建和使用"""
    print("🧪 測試簽名創建和使用...")
    
    try:
        import dspy
        from src.core.dspy.setup import initialize_dspy, cleanup_dspy
        
        # 初始化 DSPy
        if initialize_dspy():
            print("✅ DSPy 初始化成功")
            
            # 創建一個簡單的模組來測試簽名
            class SimpleModule(dspy.Module):
                def __init__(self):
                    super().__init__()
                    self.predictor = dspy.ChainOfThought("input_text -> output_text")
                
                def forward(self, input_text):
                    return self.predictor(input_text=input_text)
            
            # 創建模組實例
            module = SimpleModule()
            print("✅ 簡單模組創建成功")
            
            cleanup_dspy()
        else:
            print("❌ DSPy 初始化失敗")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 簽名創建測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 測試工作的 DSPy Signatures...")
    print("=" * 50)
    
    success1 = test_working_signature()
    print()
    success2 = test_signature_creation()
    
    print("=" * 50)
    if success1 and success2:
        print("🎉 所有測試通過！")
    else:
        print("⚠️ 部分測試失敗")