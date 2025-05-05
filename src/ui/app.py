import gradio as gr
import os
import tempfile
import time
from typing import List, Dict, Any, Tuple, Optional

from .client import ApiClient
from .components import create_character_selector, create_response_format_selector, create_dialogue_interface

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
            gr.Markdown("使用此界面與虛擬病患進行對話。您可以選擇不同的角色進行對話。")
            
            # 創建會話狀態
            character_id = gr.State("1")  # 默認角色 ID
            session_id_text = gr.State(None)  # 文本對話會話 ID
            session_id_audio = gr.State(None)  # 語音對話會話 ID
            
            # 使用標籤頁創建兩種不同的界面
            with gr.Tabs() as tabs:
                # 文本對話標籤頁
                with gr.TabItem("文本對話"):
                    with gr.Row():
                        with gr.Column(scale=3):
                            # 創建聊天區
                            text_chatbot = gr.Chatbot(label="對話歷史", height=500)
                            
                            with gr.Row():
                                # 文本輸入
                                text_input = gr.Textbox(placeholder="輸入訊息...", label="文本輸入", lines=2)
                                # 發送按鈕
                                text_send_btn = gr.Button("發送", variant="primary")
                        
                        with gr.Column(scale=1):
                            gr.Markdown("### 系統設置")
                            
                            # 角色選擇器（文本對話）
                            text_selector, text_character_map = create_character_selector(self.api_client)
                            
                            # 顯示會話ID (隱藏)
                            text_session_display = gr.Textbox(label="會話 ID", visible=False)
                            
                            # 重置按鈕
                            text_reset_btn = gr.Button("重置對話")
                
                # 語音對話標籤頁
                with gr.TabItem("語音對話"):
                    with gr.Row():
                        with gr.Column(scale=3):
                            # 創建聊天區
                            audio_chatbot = gr.Chatbot(label="對話歷史", height=500)
                            
                            # 語音輸入區
                            audio_input = gr.Audio(
                                label="語音輸入",
                                type="filepath", 
                                sources=["microphone"]
                            )
                        
                        with gr.Column(scale=1):
                            gr.Markdown("### 系統設置")
                            
                            # 角色選擇器（語音對話）
                            audio_selector, audio_character_map = create_character_selector(self.api_client)
                            
                            # 顯示會話ID (隱藏)
                            audio_session_display = gr.Textbox(label="會話 ID", visible=False)
                            
                            # 重置按鈕
                            audio_reset_btn = gr.Button("重置對話")
            
            # 定義處理函數
            def handle_text_input(text, history, char_id, sess_id):
                """處理文本輸入"""
                if not text.strip():
                    return "", history, sess_id
                
                # 更新 API 客戶端設置
                self.api_client.set_character(char_id)
                if sess_id:
                    self.api_client.session_id = sess_id
                
                # 添加用戶輸入到聊天歷史
                history = history + [[text, None]]
                
                # 發送請求
                response = self.api_client.send_text_message(text, "text")
                
                # 處理文本回應
                if "responses" in response and response["responses"]:
                    # 更新會話 ID
                    if "session_id" in response:
                        sess_id = response["session_id"]
                    
                    # 更新聊天歷史
                    history[-1][1] = response["responses"][0]
                else:
                    # 處理錯誤
                    history[-1][1] = "發生錯誤，無法獲取回應。"
                
                return "", history, sess_id
            
            def handle_audio_input(audio_path, history, char_id, sess_id):
                """處理音頻輸入"""
                if not audio_path:
                    return history, sess_id
                
                # 更新 API 客戶端設置
                self.api_client.set_character(char_id)
                if sess_id:
                    self.api_client.session_id = sess_id
                
                # 添加用戶輸入到聊天歷史
                history = history + [["[語音輸入]", None]]
                
                # 發送請求
                response = self.api_client.send_audio_message(audio_path, "text")
                
                # 處理文本回應
                if "responses" in response and response["responses"]:
                    # 更新會話 ID
                    if "session_id" in response:
                        sess_id = response["session_id"]
                    
                    # 更新聊天歷史
                    history[-1][1] = response["responses"][0]
                else:
                    # 處理錯誤
                    history[-1][1] = "發生錯誤，無法獲取回應。"
                
                return history, sess_id
            
            def handle_reset_text():
                """重置文本對話"""
                self.api_client.reset_session()
                return [], None
            
            def handle_reset_audio():
                """重置語音對話"""
                self.api_client.reset_session()
                return [], None
            
            def update_text_character(char_name):
                """更新文本對話角色選擇"""
                char_id = text_character_map.get(char_name, "1")
                self.api_client.set_character(char_id)
                return char_id, None  # 重置會話ID
            
            def update_audio_character(char_name):
                """更新語音對話角色選擇"""
                char_id = audio_character_map.get(char_name, "1")
                self.api_client.set_character(char_id)
                return char_id, None  # 重置會話ID
            
            # 設置文本對話事件處理
            text_send_btn.click(
                fn=handle_text_input,
                inputs=[text_input, text_chatbot, character_id, session_id_text],
                outputs=[text_input, text_chatbot, session_id_text]
            )
            
            text_input.submit(
                fn=handle_text_input,
                inputs=[text_input, text_chatbot, character_id, session_id_text],
                outputs=[text_input, text_chatbot, session_id_text]
            )
            
            text_reset_btn.click(
                fn=handle_reset_text,
                inputs=[],
                outputs=[text_chatbot, session_id_text]
            )
            
            text_selector.change(
                fn=update_text_character,
                inputs=[text_selector],
                outputs=[character_id, session_id_text]
            )
            
            # 設置語音對話事件處理
            audio_input.stop(
                fn=handle_audio_input,
                inputs=[audio_input, audio_chatbot, character_id, session_id_audio],
                outputs=[audio_chatbot, session_id_audio]
            )
            
            audio_reset_btn.click(
                fn=handle_reset_audio,
                inputs=[],
                outputs=[audio_chatbot, session_id_audio]
            )
            
            audio_selector.change(
                fn=update_audio_character,
                inputs=[audio_selector],
                outputs=[character_id, session_id_audio]
            )
            
            # 監視並顯示會話ID (用於調試)
            session_id_text.change(
                fn=lambda s: s if s else "尚未建立會話",
                inputs=[session_id_text],
                outputs=[text_session_display]
            )
            
            session_id_audio.change(
                fn=lambda s: s if s else "尚未建立會話",
                inputs=[session_id_audio],
                outputs=[audio_session_display]
            )
        
        # 返回所有組件
        return {
            "app": app,
            "text_chatbot": text_chatbot,
            "text_input": text_input,
            "audio_input": audio_input,
            "text_selector": text_selector,
            "audio_selector": audio_selector,
            "text_send_btn": text_send_btn,
            "text_reset_btn": text_reset_btn,
            "audio_reset_btn": audio_reset_btn
        }
    
    def launch(self, **kwargs):
        """啟動 Gradio 應用
        
        Args:
            **kwargs: 傳遞給 Gradio launch 方法的參數
        """
        try:
            return self.app.launch(**kwargs)
        finally:
            self._cleanup_temp_files()
    
    def _cleanup_temp_files(self):
        """清理臨時文件"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"清理臨時文件時出錯: {e}")

def create_app(api_url: str = "http://120.126.51.6:8000") -> DialogueApp:
    """創建醫護對話應用
    
    Args:
        api_url: API 服務器的 URL
        
    Returns:
        DialogueApp 實例
    """
    return DialogueApp(api_url) 