import gradio as gr
import os
import tempfile
import time
from typing import List, Dict, Any, Tuple, Optional

from .client import ApiClient
from .components import create_character_selector, create_response_format_selector, create_chat_ui

class DialogueApp:
    """對話系統應用類別"""
    
    def __init__(self, api_url: str = "http://120.126.51.6:8000"):
        """初始化對話應用
        
        Args:
            api_url: API 服務器的 URL
        """
        self.api_client = ApiClient(api_url)
        self.response_format = "text"  # 默認為文本回應
        self.temp_files = []  # 追蹤臨時文件以便清理
        
        # 創建 Gradio 介面
        self.ui_components = self._build_interface()
        self.app = self.ui_components["app"]
    
    def _build_interface(self) -> Dict[str, Any]:
        """建立 Gradio 界面
        
        Returns:
            UI 組件字典
        """
        # 創建基本界面
        with gr.Blocks(theme=gr.themes.Soft(), title="醫護對話系統") as app:
            gr.Markdown("# 醫護對話系統")
            gr.Markdown("使用此界面與虛擬病患進行對話。您可以選擇不同的角色和回應格式。")
            
            # 創建會話狀態
            character_id = gr.State("1")  # 默認角色 ID
            session_id = gr.State(None)
            
            with gr.Row():
                with gr.Column(scale=3):
                    # 創建聊天區
                    chatbot = gr.Chatbot(label="對話歷史", height=500)
                    
                    with gr.Row():
                        # 文本輸入
                        text_input = gr.Textbox(placeholder="輸入訊息...", label="文本輸入", lines=2)
                        # 發送按鈕
                        send_btn = gr.Button("發送", variant="primary")
                    
                    # 語音輸入/輸出區
                    with gr.Accordion("語音輸入/輸出", open=False):
                        audio_input = gr.Audio(label="錄音輸入", sources=["microphone"], type="filepath")
                        audio_output = gr.Audio(label="語音回應", type="filepath", visible=True)
                
                with gr.Column(scale=1):
                    gr.Markdown("### 系統設置")
                    
                    # 角色選擇器
                    selector, character_map = create_character_selector(self.api_client)
                    
                    # 回應格式選擇
                    format_selector = create_response_format_selector()
                    
                    # 顯示會話ID (隱藏)
                    session_display = gr.Textbox(label="會話 ID", visible=False)
                    
                    # 重置按鈕
                    reset_btn = gr.Button("重置對話")
            
            # 定義處理函數
            def handle_text_input(text, history, char_id, sess_id, resp_format):
                """處理文本輸入"""
                if not text.strip():
                    return "", history, sess_id
                
                # 更新 API 客戶端設置
                self.api_client.set_character(char_id)
                if sess_id:
                    self.api_client.session_id = sess_id
                
                # 添加用戶輸入到聊天歷史
                history = history + [[text, None]]
                
                # 轉換回應格式
                api_format = "audio" if resp_format == "音頻" else "text"
                
                # 發送請求
                response = self.api_client.send_text_message(text, api_format)
                
                # 處理音頻回應
                if api_format == "audio" and "audio_file" in response:
                    # 添加臨時文件到清理列表
                    self.temp_files.append(response["audio_file"])
                    
                    # 更新會話 ID
                    sess_id = response.get("session_id")
                    
                    # 更新聊天歷史 (使用音頻回應提示)
                    history[-1][1] = "回應以語音形式提供。"
                    
                    # 返回更新的狀態和音頻文件
                    return "", history, sess_id, response["audio_file"]
                
                # 處理文本回應
                if "responses" in response and response["responses"]:
                    # 更新會話 ID
                    sess_id = response.get("session_id")
                    
                    # 更新聊天歷史
                    history[-1][1] = response["responses"][0]
                    
                    # 返回更新的狀態
                    return "", history, sess_id, None
                
                # 處理錯誤
                history[-1][1] = "發生錯誤，無法獲取回應。"
                return "", history, sess_id, None
            
            def handle_audio_input(audio_path, history, char_id, sess_id, resp_format):
                """處理音頻輸入"""
                if not audio_path:
                    return history, sess_id, None
                
                # 更新 API 客戶端設置
                self.api_client.set_character(char_id)
                if sess_id:
                    self.api_client.session_id = sess_id
                
                # 添加用戶輸入到聊天歷史 (語音輸入提示)
                history = history + [["[語音輸入]", None]]
                
                # 轉換回應格式
                api_format = "audio" if resp_format == "音頻" else "text"
                
                # 發送請求
                response = self.api_client.send_audio_message(audio_path, api_format)
                
                # 處理音頻回應
                if api_format == "audio" and "audio_file" in response:
                    # 添加臨時文件到清理列表
                    self.temp_files.append(response["audio_file"])
                    
                    # 更新會話 ID
                    sess_id = response.get("session_id")
                    
                    # 更新聊天歷史
                    history[-1][1] = "回應以語音形式提供。"
                    
                    # 返回更新的狀態和音頻文件
                    return history, sess_id, response["audio_file"]
                
                # 處理文本回應
                if "responses" in response and response["responses"]:
                    # 更新會話 ID
                    sess_id = response.get("session_id")
                    
                    # 更新聊天歷史
                    history[-1][1] = response["responses"][0]
                    
                    # 返回更新的狀態
                    return history, sess_id, None
                
                # 處理錯誤
                history[-1][1] = "發生錯誤，無法獲取回應。"
                return history, sess_id, None
            
            def handle_reset():
                """重置對話"""
                self.api_client.reset_session()
                return [], None
            
            def update_character(char_name):
                """更新角色選擇"""
                char_id = character_map.get(char_name, "1")
                self.api_client.set_character(char_id)
                return char_id, None  # 重置會話ID
            
            def update_format(format_choice):
                """更新回應格式"""
                self.response_format = "audio" if format_choice == "音頻" else "text"
                # 更新音頻輸出可見性
                audio_visible = self.response_format == "audio"
                return gr.Audio.update(visible=audio_visible)
            
            # 設置事件處理
            send_btn.click(
                fn=handle_text_input,
                inputs=[text_input, chatbot, character_id, session_id, format_selector],
                outputs=[text_input, chatbot, session_id, audio_output]
            )
            
            text_input.submit(
                fn=handle_text_input,
                inputs=[text_input, chatbot, character_id, session_id, format_selector],
                outputs=[text_input, chatbot, session_id, audio_output]
            )
            
            audio_input.stop(
                fn=handle_audio_input,
                inputs=[audio_input, chatbot, character_id, session_id, format_selector],
                outputs=[chatbot, session_id, audio_output]
            )
            
            reset_btn.click(
                fn=handle_reset,
                inputs=[],
                outputs=[chatbot, session_id]
            )
            
            selector.change(
                fn=update_character,
                inputs=[selector],
                outputs=[character_id, session_id]
            )
            
            format_selector.change(
                fn=update_format,
                inputs=[format_selector],
                outputs=[audio_output]
            )
            
            # 監視並顯示會話ID (用於調試)
            session_id.change(
                fn=lambda s: s if s else "尚未建立會話",
                inputs=[session_id],
                outputs=[session_display]
            )
        
        # 返回所有組件
        return {
            "app": app,
            "chatbot": chatbot,
            "text_input": text_input,
            "audio_input": audio_input,
            "audio_output": audio_output,
            "character_selector": selector,
            "format_selector": format_selector,
            "send_btn": send_btn,
            "reset_btn": reset_btn,
            "session_display": session_display
        }
    
    def launch(self, **kwargs):
        """啟動 Gradio 應用
        
        Args:
            **kwargs: 傳遞給 Gradio launch 方法的參數
        """
        # 配置默認參數
        default_kwargs = {
            "server_name": "0.0.0.0",
            "server_port": 7860,
            "share": False,
            "debug": False
        }
        
        # 合併用戶提供的參數
        launch_kwargs = {**default_kwargs, **kwargs}
        
        try:
            # 啟動應用
            self.app.launch(**launch_kwargs)
        finally:
            # 清理臨時文件
            self._cleanup_temp_files()
    
    def _cleanup_temp_files(self):
        """清理應用創建的臨時文件"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"清理臨時文件時出錯: {e}")

# 創建應用實例的輔助函數
def create_app(api_url: str = "http://120.126.51.6:8000") -> DialogueApp:
    """創建對話應用實例
    
    Args:
        api_url: API 服務器的 URL
        
    Returns:
        DialogueApp 實例
    """
    return DialogueApp(api_url) 