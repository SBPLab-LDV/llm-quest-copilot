import gradio as gr
import os
import logging
from typing import List, Dict, Any, Optional, Callable

# 設置日誌記錄
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ui_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ui_components")

def create_character_selector(api_client, on_change: Optional[Callable] = None):
    """創建角色選擇器組件
    
    Args:
        api_client: API 客戶端
        on_change: 選擇改變時的回調函數
        
    Returns:
        角色選擇器組件
    """
    # 獲取角色列表
    characters = api_client.get_characters()
    
    # 如果無法獲取角色，使用默認值
    if not characters:
        characters = [{"id": "1", "name": "默認病患"}]
    
    # 創建角色選項
    character_names = [char["name"] for char in characters]
    character_ids = {char["name"]: char["id"] for char in characters}
    
    # 創建下拉選單
    selector = gr.Dropdown(
        choices=character_names,
        value=character_names[0],
        label="選擇病患角色",
        interactive=True
    )
    
    # 如果提供了回調函數，則設置變更事件
    if on_change:
        selector.change(
            fn=lambda name: on_change(character_ids[name]),
            inputs=[selector]
        )
    
    return selector, character_ids

def create_response_format_selector(on_change: Optional[Callable] = None):
    """創建回應格式選擇器
    
    Args:
        on_change: 選擇改變時的回調函數
        
    Returns:
        回應格式選擇器組件
    """
    selector = gr.Radio(
        choices=["文本", "音頻"],
        value="文本",
        label="回應格式",
        interactive=True
    )
    
    # 如果提供了回調函數，則設置變更事件
    if on_change:
        selector.change(
            fn=lambda format_type: on_change("audio" if format_type == "音頻" else "text"),
            inputs=[selector]
        )
    
    return selector

def create_dialogue_interface():
    """創建對話界面組件
    
    Returns:
        對話界面組件和音頻組件
    """
    # 創建聊天界面
    chatbot = gr.Chatbot(
        label="對話歷史",
        height=500,
        show_copy_button=True
    )
    
    # 創建文本輸入
    text_input = gr.Textbox(
        placeholder="輸入訊息...",
        label="文本輸入",
        lines=2
    )
    
    # 創建音頻輸入和輸出組件
    audio_input = gr.Audio(
        label="語音輸入",
        type="filepath", 
        sources=["microphone"]
    )
    
    audio_output = gr.Audio(
        label="語音回應",
        type="filepath",
        visible=False
    )
    
    # 創建按鈕
    send_btn = gr.Button("發送訊息", variant="primary")
    reset_btn = gr.Button("重置對話")
    
    return {
        "chatbot": chatbot,
        "text_input": text_input,
        "audio_input": audio_input,
        "audio_output": audio_output,
        "send_btn": send_btn,
        "reset_btn": reset_btn
    }

def create_chat_ui():
    """創建完整聊天 UI
    
    Returns:
        UI 組件集合
    """
    with gr.Blocks(theme=gr.themes.Soft(), title="醫護對話系統") as app:
        gr.Markdown("# 醫護對話系統")
        gr.Markdown("使用此界面與虛擬病患進行對話。您可以選擇不同的角色和回應格式。")
        
        with gr.Row():
            with gr.Column(scale=3):
                # 使用函數創建對話界面
                dialogue_components = create_dialogue_interface()
                
            with gr.Column(scale=1):
                gr.Markdown("### 系統設置")
                
                # 這些選擇器將在 app.py 中完成功能配置
                character_selector = gr.Dropdown(
                    choices=["載入中..."],
                    label="選擇病患角色",
                    interactive=True
                )
                
                response_format = gr.Radio(
                    choices=["文本", "音頻"],
                    value="文本",
                    label="回應格式",
                    interactive=True
                )
                
                session_info = gr.Textbox(
                    label="會話 ID",
                    interactive=False,
                    visible=False
                )
        
        # 返回所有組件
        return {
            **dialogue_components,
            "character_selector": character_selector,
            "response_format": response_format,
            "session_info": session_info
        }

def create_custom_character_interface():
    """創建自定義角色界面
    
    Returns:
        自定義角色界面組件集合
    """
    with gr.Accordion("自定義角色", open=False) as accordion:
        use_custom_config = gr.Checkbox(label="使用自定義角色", value=False)
        
        with gr.Group(visible=False) as custom_fields:
            name = gr.Textbox(label="角色名稱", placeholder="例如：林小明")
            persona = gr.Textbox(label="角色個性", placeholder="例如：積極樂觀，善於溝通", lines=2)
            backstory = gr.Textbox(label="角色背景", placeholder="例如：32歲，銀行職員，已婚", lines=3)
            goal = gr.Textbox(label="對話目標", placeholder="例如：尋求醫生關於頭痛的建議", lines=2)
            
            fixed_settings = gr.Textbox(
                label="固定設定",
                placeholder="格式：鍵:值\n例如：\n流水編號:1\n年齡:69\n性別:男\n診斷:齒齦癌\n分期:pT2N0M0, stage II",
                lines=8
            )
            
            floating_settings = gr.Textbox(
                label="浮動設定",
                placeholder="格式：鍵:值\n例如：\n目前接受治療場所:病房\n目前治療階段:手術後/出院前\n關鍵字:傷口\n個案現況:病人右臉頰縫線持續有黃色分泌物",
                lines=8
            )
    
    # 設置交互邏輯：勾選使用自定義角色時顯示字段
    use_custom_config.change(
        fn=lambda x: gr.update(visible=x),
        inputs=[use_custom_config],
        outputs=[custom_fields]
    )
    
    # 定義生成配置的函數
    def generate_config(use_custom, name, persona, backstory, goal, fixed, floating):
        logger.info("開始生成自定義角色配置")
        logger.debug(f"輸入參數：\nuse_custom: {use_custom}\nname: {name}\npersona: {persona}\nbackstory: {backstory}\ngoal: {goal}")
        logger.debug(f"固定設定原始輸入：\n{fixed}")
        logger.debug(f"浮動設定原始輸入：\n{floating}")
        
        if not use_custom:
            logger.info("未使用自定義角色，返回 None")
            return None
        
        # 中文鍵名到英文的映射表
        cn_to_en_mapping = {
            # 固定設定常見鍵名
            "流水編號": "serial_number",
            "年齡": "age",
            "性別": "gender", 
            "診斷": "diagnosis",
            "分期": "stage",
            # 浮動設定常見鍵名
            "目前接受治療場所": "current_treatment_location",
            "目前治療階段": "current_treatment_stage",
            "關鍵字": "keywords",
            "個案現況": "current_status",
            "現況": "current_condition"
        }
        
        # 解析固定設定
        fixed_dict = {}
        for line in fixed.split('\n'):
            if ':' in line and line.strip():
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # 檢查並轉換中文鍵名到英文
                en_key = cn_to_en_mapping.get(key, key)
                logger.debug(f"將固定設定鍵名 '{key}' 映射為 '{en_key}'")
                
                # 嘗試將數值轉換為整數或浮點數
                if value.isdigit():
                    fixed_dict[en_key] = int(value)
                else:
                    try:
                        fixed_dict[en_key] = float(value)
                    except ValueError:
                        fixed_dict[en_key] = value
        logger.debug(f"解析後的固定設定：{fixed_dict}")
        
        # 解析浮動設定
        floating_dict = {}
        for line in floating.split('\n'):
            if ':' in line and line.strip():
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # 檢查並轉換中文鍵名到英文
                en_key = cn_to_en_mapping.get(key, key)
                logger.debug(f"將浮動設定鍵名 '{key}' 映射為 '{en_key}'")
                
                # 嘗試將數值轉換為整數或浮點數
                if value.isdigit():
                    floating_dict[en_key] = int(value)
                else:
                    try:
                        floating_dict[en_key] = float(value)
                    except ValueError:
                        floating_dict[en_key] = value
        logger.debug(f"解析後的浮動設定：{floating_dict}")
        
        # 創建標準格式的配置
        config = {
            "name": name,
            "persona": persona,
            "backstory": backstory,
            "goal": goal,
            "details": {
                "fixed_settings": fixed_dict,
                "floating_settings": floating_dict
            }
        }
        logger.info("成功生成配置")
        logger.debug(f"最終配置：{config}")
        return config
    
    return {
        "accordion": accordion,
        "use_custom_config": use_custom_config,
        "name": name,
        "persona": persona,
        "backstory": backstory,
        "goal": goal,
        "fixed_settings": fixed_settings,
        "floating_settings": floating_settings,
        "custom_fields": custom_fields,
        "generate_config": generate_config
    } 