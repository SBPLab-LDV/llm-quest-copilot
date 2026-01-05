"""
DSPy Signatures 定義

定義用於對話系統的各種 DSPy Signatures，
用於結構化定義輸入輸出格式。
"""

import dspy
from typing import List, Dict, Any, Optional

class PatientResponseSignature(dspy.Signature):
    """生成病患回應的簽名

    這是核心的病患回應生成簽名，用於根據對話方的輸入
    生成多個可能的病患回應選項。
    """

    # 輸入欄位 - 對話方和對話相關信息
    user_input = dspy.InputField(desc="對話方的輸入或問題")
    character_name = dspy.InputField(desc="病患角色的名稱")
    character_persona = dspy.InputField(desc="病患的個性描述")
    character_backstory = dspy.InputField(desc="病患的背景故事")
    character_goal = dspy.InputField(desc="病患的目標")
    character_details = dspy.InputField(desc="病患的詳細設定，包含固定和浮動設定的YAML格式字符串")
    conversation_history = dspy.InputField(desc="最近的對話歷史，以換行分隔")
    
    # 輸出欄位 - 病患的回應
    reasoning = dspy.OutputField(desc="推理過程和思考步驟")
    responses = dspy.OutputField(desc="4個不同的病患回應選項，每個都應該是完整的句子，格式為JSON陣列")
    state = dspy.OutputField(desc="對話狀態：必須是 NORMAL、CONFUSED、TRANSITIONING 或 TERMINATED 其中之一")
    dialogue_context = dspy.OutputField(desc="當前對話情境，如：醫師查房、病房日常、生命徵象相關、身體評估等")

class ContextClassificationSignature(dspy.Signature):
    """對話情境分類簽名
    
    用於判斷當前對話屬於哪種醫療情境。
    """
    
    # 輸入欄位
    user_input = dspy.InputField(desc="對話方的輸入")
    available_contexts = dspy.InputField(desc="可用的對話情境列表，YAML格式")
    conversation_history = dspy.InputField(desc="對話歷史")
    
    # 輸出欄位
    reasoning = dspy.OutputField(desc="分類的推理過程")
    context = dspy.OutputField(desc="識別出的對話情境名稱")
    confidence = dspy.OutputField(desc="分類信心度，0.0到1.0之間")

class ResponseEvaluationSignature(dspy.Signature):
    """回應評估簽名
    
    用於評估生成的病患回應的品質。
    """
    
    # 輸入欄位
    user_input = dspy.InputField(desc="對話方的原始輸入")
    character_info = dspy.InputField(desc="病患角色信息")
    generated_responses = dspy.InputField(desc="生成的回應選項列表")
    dialogue_context = dspy.InputField(desc="對話情境")
    
    # 輸出欄位
    quality_score = dspy.OutputField(desc="整體品質評分，0.0到1.0之間")
    appropriateness_score = dspy.OutputField(desc="適當性評分，0.0到1.0之間")
    diversity_score = dspy.OutputField(desc="回應多樣性評分，0.0到1.0之間")
    feedback = dspy.OutputField(desc="改進建議或評估說明")

class StateTransitionSignature(dspy.Signature):
    """狀態轉換判斷簽名
    
    用於判斷對話是否需要轉換狀態。
    """
    
    # 輸入欄位
    current_state = dspy.InputField(desc="當前對話狀態")
    user_input = dspy.InputField(desc="對話方的輸入")
    character_condition = dspy.InputField(desc="病患當前的身體狀況")
    conversation_context = dspy.InputField(desc="對話上下文")
    
    # 輸出欄位
    new_state = dspy.OutputField(desc="建議的新狀態：NORMAL、CONFUSED、TRANSITIONING 或 TERMINATED")
    reason = dspy.OutputField(desc="狀態轉換的原因說明")
    should_transition = dspy.OutputField(desc="是否應該轉換狀態")

class ExampleRetrievalSignature(dspy.Signature):
    """範例檢索簽名
    
    用於從範例庫中檢索最相關的 few-shot examples。
    """
    
    # 輸入欄位
    query = dspy.InputField(desc="查詢內容，通常是對話方的輸入")
    context = dspy.InputField(desc="對話情境")
    available_examples = dspy.InputField(desc="可用的範例列表")
    max_examples = dspy.InputField(desc="最大返回範例數量")
    
    # 輸出欄位
    selected_examples = dspy.OutputField(desc="選中的範例列表")
    relevance_scores = dspy.OutputField(desc="每個範例的相關度評分")

class DialogueConsistencySignature(dspy.Signature):
    """對話一致性檢查簽名

    用於確保對話回應與角色設定和歷史保持一致。
    """
    
    # 輸入欄位
    character_profile = dspy.InputField(desc="完整的角色檔案")
    conversation_history = dspy.InputField(desc="對話歷史")
    proposed_response = dspy.InputField(desc="提議的回應")
    
    # 輸出欄位
    is_consistent = dspy.OutputField(desc="回應是否與角色和歷史一致")
    consistency_score = dspy.OutputField(desc="一致性評分，0.0到1.0之間")
    inconsistency_details = dspy.OutputField(desc="如果不一致，說明具體的不一致之處")


class AudioDisfluencyChatSignature(dspy.Signature):
    """語音任務 system/user prompt 組裝簽名。"""

    character_profile = dspy.InputField(desc="角色摘要（姓名/診斷/目標）")
    conversation_history = dspy.InputField(desc="近期對話歷史（含角色提醒）")
    available_contexts = dspy.InputField(desc="可用情境清單")
    template_rules = dspy.InputField(desc="輸出格式與禁止事項說明")
    option_count = dspy.InputField(desc="預期產生的選項數")

    system_prompt = dspy.OutputField(desc="最終 system prompt 內容")
    user_prompt = dspy.OutputField(desc="最終 user prompt 內容")

# 工具函數：簽名驗證和測試
def validate_signature_output(signature_class, output_data: Dict[str, Any]) -> bool:
    """驗證簽名輸出是否符合格式要求
    
    Args:
        signature_class: 簽名類別
        output_data: 輸出數據
        
    Returns:
        是否符合格式要求
    """
    try:
        # 檢查必要欄位
        output_fields = {name: field for name, field in signature_class.__annotations__.items() 
                        if hasattr(signature_class.__dict__.get(name), 'json_schema_extra')}
        
        for field_name in output_fields:
            if field_name not in output_data:
                return False
        
        return True
        
    except Exception:
        return False

def get_signature_info(signature_class) -> Dict[str, Any]:
    """獲取簽名信息
    
    Args:
        signature_class: 簽名類別
        
    Returns:
        簽名信息字典
    """
    info = {
        'name': signature_class.__name__,
        'description': signature_class.__doc__,
        'input_fields': [],
        'output_fields': []
    }
    
    # 解析欄位信息
    for field_name, field_type in signature_class.__annotations__.items():
        field_obj = getattr(signature_class, field_name, None)
        
        if field_obj and hasattr(field_obj, 'json_schema_extra'):
            field_info = {
                'name': field_name,
                'type': str(field_type),
                'description': field_obj.json_schema_extra.get('desc', ''),
            }
            
            # 判斷是輸入還是輸出欄位
            if isinstance(field_obj, dspy.InputField):
                info['input_fields'].append(field_info)
            elif isinstance(field_obj, dspy.OutputField):
                info['output_fields'].append(field_info)
    
    return info

# 預定義的簽名列表，用於批量操作
AVAILABLE_SIGNATURES = {
    'patient_response': PatientResponseSignature,
    'context_classification': ContextClassificationSignature,
    'response_evaluation': ResponseEvaluationSignature,
    'state_transition': StateTransitionSignature,
    'example_retrieval': ExampleRetrievalSignature,
    'dialogue_consistency': DialogueConsistencySignature,
    'audio_disfluency_chat': AudioDisfluencyChatSignature,
}

def get_all_signature_info() -> Dict[str, Dict[str, Any]]:
    """獲取所有簽名的信息
    
    Returns:
        所有簽名信息的字典
    """
    return {name: get_signature_info(sig_class) 
            for name, sig_class in AVAILABLE_SIGNATURES.items()}

# 測試函數
def test_signatures():
    """測試所有簽名定義"""
    print("測試 DSPy Signatures...")
    
    try:
        # 測試簽名創建
        for name, sig_class in AVAILABLE_SIGNATURES.items():
            print(f"測試簽名: {name}")
            
            # 檢查簽名是否是 dspy.Signature 的子類
            if not issubclass(sig_class, dspy.Signature):
                print(f"❌ {name} 不是 dspy.Signature 的子類")
                return False
            
            # 獲取簽名信息
            info = get_signature_info(sig_class)
            print(f"  輸入欄位: {len(info['input_fields'])} 個")
            print(f"  輸出欄位: {len(info['output_fields'])} 個")
        
        print("✅ 所有簽名測試通過")
        return True
        
    except Exception as e:
        print(f"❌ 簽名測試失敗: {e}")
        return False

if __name__ == "__main__":
    test_signatures()
