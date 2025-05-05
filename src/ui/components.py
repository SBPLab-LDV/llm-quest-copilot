import gradio as gr
import os
from typing import List, Dict, Any, Optional, Callable

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