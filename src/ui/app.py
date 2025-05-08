import gradio as gr
import os
import tempfile
import time
import json
import logging
import sys
import inspect
from typing import List, Dict, Any, Tuple, Optional

from .client import ApiClient
from .components import create_character_selector, create_response_format_selector, create_dialogue_interface, create_custom_character_interface

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
log_file_path = os.path.join(project_root, 'ui_debug.log')

# 設置日誌記錄
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file_path, mode='w')  # Use 'w' mode to overwrite the file each time
    ]
)
logger = logging.getLogger(__name__)

# Log some debug info at startup
logger.info(f"Starting UI application")
logger.info(f"Log file path: {log_file_path}")
logger.info(f"Current directory: {current_dir}")
logger.info(f"Project root: {project_root}")

def log_function_call(func):
    """Function decorator for logging purposes"""
    def wrapper(*args, **kwargs):
        logger.info(f"Calling function: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Function {func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in function {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper

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
            custom_config = gr.State(None)  # 自定義角色配置
            
            # 使用標籤頁創建兩種不同的界面
            with gr.Tabs() as tabs:
                # 文本對話標籤頁
                with gr.TabItem("文本對話"):
                    with gr.Row():
                        with gr.Column(scale=3):
                            # 創建聊天區
                            text_chatbot = gr.Chatbot(label="對話歷史", height=500)
                            
                            # 添加回應選項區
                            with gr.Column(visible=False, elem_id="response_box", scale=1) as response_box:
                                gr.Markdown("### 病患回應選項")
                                response_options = gr.State([])  # 存儲回應選項
                                
                                # 創建5個固定的回應按鈕，初始隱藏
                                with gr.Column(visible=True) as response_buttons_container:
                                    response_btn1 = gr.Button("選項1", visible=False)
                                    response_btn2 = gr.Button("選項2", visible=False)
                                    response_btn3 = gr.Button("選項3", visible=False)
                                    response_btn4 = gr.Button("選項4", visible=False)
                                    response_btn5 = gr.Button("選項5", visible=False)
                            
                            with gr.Row():
                                # 文本輸入
                                text_input = gr.Textbox(placeholder="輸入訊息...", label="文本輸入", lines=2)
                                # 發送按鈕
                                text_send_btn = gr.Button("發送", variant="primary")
                        
                        with gr.Column(scale=1):
                            gr.Markdown("### 系統設置")
                            
                            # 角色選擇器（文本對話）
                            text_selector, text_character_map = create_character_selector(self.api_client)
                            
                            # 創建自定義角色界面
                            text_custom_char = create_custom_character_interface()
                            
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
                            
                            # 創建自定義角色界面
                            audio_custom_char = create_custom_character_interface()
                            
                            # 顯示會話ID (隱藏)
                            audio_session_display = gr.Textbox(label="會話 ID", visible=False)
                            
                            # 重置按鈕
                            audio_reset_btn = gr.Button("重置對話")
            
            # 定義處理函數
            @log_function_call
            def update_response_buttons(response_list):
                """更新回應選項按鈕顯示"""
                logger.info(f"更新回應按鈕: {response_list}")
                
                # Debug button states before update
                logger.info(f"BUTTON STATE BEFORE UPDATE:")
                logger.info(f"Button 1: visible={response_btn1.visible}, value='{response_btn1.value}'")
                logger.info(f"Button 2: visible={response_btn2.visible}, value='{response_btn2.value}'")
                logger.info(f"Button 3: visible={response_btn3.visible}, value='{response_btn3.value}'")
                logger.info(f"Button 4: visible={response_btn4.visible}, value='{response_btn4.value}'")
                logger.info(f"Button 5: visible={response_btn5.visible}, value='{response_btn5.value}'")
                
                # 更新回應框的可見性
                if not response_list or len(response_list) == 0:
                    logger.info("沒有回應選項，隱藏所有按鈕")
                    # 直接更新組件而不是返回字典
                    response_box.visible = False
                    response_btn1.visible = False
                    response_btn1.value = ""
                    response_btn2.visible = False
                    response_btn2.value = ""
                    response_btn3.visible = False
                    response_btn3.value = ""
                    response_btn4.visible = False
                    response_btn4.value = ""
                    response_btn5.visible = False
                    response_btn5.value = ""
                    
                    return {
                        response_box: gr.update(visible=False),
                        response_btn1: gr.update(visible=False, value=""),
                        response_btn2: gr.update(visible=False, value=""),
                        response_btn3: gr.update(visible=False, value=""),
                        response_btn4: gr.update(visible=False, value=""),
                        response_btn5: gr.update(visible=False, value="")
                    }
                
                logger.info(f"顯示 {len(response_list)} 個回應按鈕")
                logger.info(f"回應內容: {response_list}")
                
                # 先直接修改組件屬性
                response_box.visible = True
                
                # 建立按鈕更新字典
                updates = {response_box: gr.update(visible=True)}
                buttons = [response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
                
                # 更新所有按鈕
                for i, button in enumerate(buttons):
                    if i < len(response_list) and response_list[i]:
                        button_text = f"{i+1}. {response_list[i]}"
                        logger.info(f"設置按鈕 {i+1} 文字: {button_text}")
                        # 直接修改按鈕屬性
                        button.visible = True
                        button.value = button_text
                        updates[button] = gr.update(visible=True, value=button_text)
                    else:
                        button.visible = False
                        button.value = ""
                        updates[button] = gr.update(visible=False, value="")
                
                # Debug button states after update
                logger.info(f"BUTTON STATE AFTER UPDATE:")
                logger.info(f"Button 1: visible={response_btn1.visible}, value='{response_btn1.value}'")
                logger.info(f"Button 2: visible={response_btn2.visible}, value='{response_btn2.value}'")
                logger.info(f"Button 3: visible={response_btn3.visible}, value='{response_btn3.value}'")
                logger.info(f"Button 4: visible={response_btn4.visible}, value='{response_btn4.value}'")
                logger.info(f"Button 5: visible={response_btn5.visible}, value='{response_btn5.value}'")
                
                logger.info(f"Updates to apply: {updates}")
                return updates
            
            @log_function_call
            def handle_text_input(text, history, char_id, sess_id, config):
                """處理文本輸入"""
                if not text.strip():
                    return "", history, sess_id, []
                
                # 更新 API 客戶端設置
                self.api_client.set_character(char_id, config)
                if sess_id:
                    self.api_client.session_id = sess_id
                
                # 添加用戶輸入到聊天歷史
                history = history + [[text, None]]
                
                # 直接更新chatbot UI
                text_chatbot.value = history
                
                # 發送請求
                logger.info(f"發送文本: {text}")
                response = self.api_client.send_text_message(text, "text")
                logger.info(f"收到回應: {response}")
                
                # 處理文本回應
                if "responses" in response and response["responses"]:
                    # 更新會話 ID
                    if "session_id" in response:
                        sess_id = response["session_id"]
                        logger.debug(f"更新會話 ID: {sess_id}")
                    
                    # 檢查是否為 CONFUSED 狀態
                    if "state" in response and response["state"] == "CONFUSED":
                        # 將 CONFUSED 狀態的回應加上提示
                        confused_response = response["responses"][0]
                        history[-1][1] = f"{confused_response} (系統暫時無法理解您的問題，請嘗試重新表述)"
                        text_chatbot.value = history  # 再次更新UI
                        logger.debug("處理 CONFUSED 狀態回應")
                        # 隱藏回應選項
                        return "", history, sess_id, []
                    else:
                        # 返回所有回應選項，供患者選擇
                        response_options_list = response["responses"]
                        logger.debug(f"回應選項數量: {len(response_options_list)}")
                        logger.debug(f"顯示回應選項: {response_options_list}")
                        return "", history, sess_id, response_options_list
                else:
                    # 處理錯誤
                    logger.warning(f"API 回應中沒有找到回應選項或回應選項為空: {response}")
                    history[-1][1] = "發生錯誤，無法獲取回應。"
                    text_chatbot.value = history  # 更新UI显示错误信息
                    # 隱藏回應選項
                    return "", history, sess_id, []
            
            def handle_audio_input(audio_path, history, char_id, sess_id, config):
                """處理音頻輸入"""
                if not audio_path:
                    return history, sess_id
                
                # 更新 API 客戶端設置
                self.api_client.set_character(char_id, config)
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
                    
                    # 檢查是否為 CONFUSED 狀態
                    if "state" in response and response["state"] == "CONFUSED":
                        # 將 CONFUSED 狀態的回應加上提示
                        confused_response = response["responses"][0]
                        history[-1][1] = f"{confused_response} (系統暫時無法理解您的問題，請嘗試重新表述)"
                    else:
                        # 正常回應
                        history[-1][1] = response["responses"][0]
                else:
                    # 處理錯誤
                    history[-1][1] = "發生錯誤，無法獲取回應。"
                
                return history, sess_id
            
            def handle_reset_text():
                """重置文本對話"""
                self.api_client.reset_session()
                return [], None, []
            
            def handle_reset_audio():
                """重置語音對話"""
                self.api_client.reset_session()
                return [], None
            
            def update_text_character(char_name, use_custom, name, persona, backstory, goal, fixed, floating):
                """更新文本對話角色選擇"""
                if use_custom:
                    # 使用自定義角色配置
                    config_fn = text_custom_char["generate_config"]
                    config = config_fn(use_custom, name, persona, backstory, goal, fixed, floating)
                    
                    # 檢查配置是否有效
                    if config and "error" not in config:
                        # 使用隨機 ID 作為自定義角色 ID
                        custom_id = f"custom_{int(time.time())}"
                        self.api_client.set_character(custom_id, config)
                        return custom_id, None, config
                    else:
                        # 配置錯誤，使用默認角色
                        char_id = text_character_map.get(char_name, "1")
                        self.api_client.set_character(char_id)
                        return char_id, None, None
                else:
                    # 使用預設角色
                    char_id = text_character_map.get(char_name, "1")
                    self.api_client.set_character(char_id)
                    return char_id, None, None
            
            def update_audio_character(char_name, use_custom, name, persona, backstory, goal, fixed, floating):
                """更新語音對話角色選擇"""
                if use_custom:
                    # 使用自定義角色配置
                    config_fn = audio_custom_char["generate_config"]
                    config = config_fn(use_custom, name, persona, backstory, goal, fixed, floating)
                    
                    # 檢查配置是否有效
                    if config and "error" not in config:
                        # 使用隨機 ID 作為自定義角色 ID
                        custom_id = f"custom_{int(time.time())}"
                        self.api_client.set_character(custom_id, config)
                        return custom_id, None, config
                    else:
                        # 配置錯誤，使用默認角色
                        char_id = audio_character_map.get(char_name, "1")
                        self.api_client.set_character(char_id)
                        return char_id, None, None
                else:
                    # 使用預設角色
                    char_id = audio_character_map.get(char_name, "1")
                    self.api_client.set_character(char_id)
                    return char_id, None, None
            
            # 處理患者選擇的回應
            @log_function_call
            def handle_response_selection(selected_response, history, sess_id):
                """處理患者選擇的回應選項"""
                logger.info(f"患者選擇的回應: {selected_response}")
                
                if not history or not selected_response:
                    logger.warning("無法處理選擇: 歷史記錄或選擇的回應為空")
                    return history, sess_id, []
                
                # 將選擇的回應添加到聊天歷史
                if history and history[-1][1] is None:
                    history[-1][1] = selected_response
                    logger.info(f"將選擇的回應添加到聊天歷史: {selected_response}")
                elif history:
                    # 如果已經有回應，則將選擇的回應替換現有的回應
                    logger.info(f"替換現有回應: {history[-1][1]} -> {selected_response}")
                    history[-1][1] = selected_response
                else:
                    # 如果歷史為空，創建一個新的對話
                    logger.info(f"創建新對話項目: {selected_response}")
                    history = [["", selected_response]]
                
                # 將選擇的回應發送給 API 客戶端以更新對話歷史
                # 重要: 這樣病患選擇的回應會被加入到 LLM 的歷史對話中，用於下一輪對話
                if sess_id:
                    try:
                        logger.info(f"發送選擇的回應到伺服器: {selected_response}, 會話ID: {sess_id}")
                        self.api_client.update_selected_response(sess_id, selected_response)
                        logger.info("成功發送選擇的回應到伺服器")
                    except Exception as e:
                        logger.error(f"發送選擇的回應時出錯: {e}", exc_info=True)
                else:
                    logger.warning("無法發送選擇的回應: 會話ID為空")
                
                # 清空回應選項
                return history, sess_id, []
            
            @log_function_call
            def handle_btn1_click(response_value):
                try:
                    # Print stack trace for debugging
                    stack = inspect.stack()
                    logger.info(f"Call stack: {[frame.function for frame in stack]}")
                    
                    # Debug button state
                    logger.info(f"Button 1 clicked - incoming value: '{response_value}'")
                    
                    if not response_value:
                        logger.warning("Button 1 has no value")
                        return text_chatbot.value, session_id_text.value, []
                    
                    response_text = response_value.split(". ", 1)[1] if ". " in response_value else response_value
                    logger.info(f"選擇回應按鈕1: {response_text}")
                    
                    # Add debugging for current chatbot state
                    logger.info(f"當前對話歷史: {text_chatbot.value}")
                    logger.info(f"當前會話ID: {session_id_text.value}")
                    
                    # Update the chat history directly
                    history = text_chatbot.value.copy() if text_chatbot.value else []
                    logger.info(f"History before update: {history}")
                    
                    # 找到最近一次用户输入的内容
                    last_user_input = "你好"  # 默认值
                    # 如果有历史记录，尝试获取最后一次用户输入
                    if history:
                        for i in range(len(history)-1, -1, -1):
                            if history[i][0]:  # 如果用户输入不为空
                                last_user_input = history[i][0]
                                break
                    
                    if history and history[-1][1] is None:
                        history[-1][1] = response_text
                        logger.info(f"更新對話歷史: {history}")
                    elif history:
                        # If there's already a response, create a new entry with the last user input
                        logger.info(f"Adding new entry to history with last user input: {last_user_input}")
                        history.append([last_user_input, response_text])
                    else:
                        # If history is empty, create a new entry
                        logger.info(f"Creating new history")
                        history = [[last_user_input, response_text]]
                    
                    logger.info(f"Updated history: {history}")
                    
                    # Force update the chatbot directly
                    text_chatbot.value = history
                    
                    # Try to send the selected response to the server
                    if session_id_text.value:
                        try:
                            logger.info(f"Sending response to server: {response_text}")
                            self.api_client.update_selected_response(session_id_text.value, response_text)
                            logger.info("Successfully sent response to server")
                        except Exception as e:
                            logger.error(f"Error sending response to server: {e}", exc_info=True)
                    else:
                        logger.warning("No session ID available, cannot send to server")
                    
                    # Return the updated history and clear response options
                    return history, session_id_text.value, []
                except Exception as e:
                    logger.error(f"Error in handle_btn1_click: {e}", exc_info=True)
                    return text_chatbot.value, session_id_text.value, []
            
            @log_function_call
            def handle_btn2_click(response_value):
                try:
                    logger.info(f"Button 2 clicked - incoming value: '{response_value}'")
                    
                    if not response_value:
                        logger.warning("Button 2 has no value")
                        return text_chatbot.value, session_id_text.value, []
                    
                    response_text = response_value.split(". ", 1)[1] if ". " in response_value else response_value
                    logger.info(f"選擇回應按鈕2: {response_text}")
                    
                    # Add debugging for current chatbot state
                    logger.info(f"當前對話歷史: {text_chatbot.value}")
                    logger.info(f"當前會話ID: {session_id_text.value}")
                    
                    # Update the chat history directly
                    history = text_chatbot.value.copy() if text_chatbot.value else []
                    logger.info(f"History before update: {history}")
                    
                    # 找到最近一次用户输入的内容
                    last_user_input = "你好"  # 默认值
                    # 如果有历史记录，尝试获取最后一次用户输入
                    if history:
                        for i in range(len(history)-1, -1, -1):
                            if history[i][0]:  # 如果用户输入不为空
                                last_user_input = history[i][0]
                                break
                    
                    if history and history[-1][1] is None:
                        history[-1][1] = response_text
                        logger.info(f"更新對話歷史: {history}")
                    elif history:
                        # If there's already a response, create a new entry with the last user input
                        logger.info(f"Adding new entry to history with last user input: {last_user_input}")
                        history.append([last_user_input, response_text])
                    else:
                        # If history is empty, create a new entry
                        logger.info(f"Creating new history")
                        history = [[last_user_input, response_text]]
                    
                    logger.info(f"Updated history: {history}")
                    
                    # Force update the chatbot directly
                    text_chatbot.value = history
                    
                    # Try to send the selected response to the server
                    if session_id_text.value:
                        try:
                            logger.info(f"Sending response to server: {response_text}")
                            self.api_client.update_selected_response(session_id_text.value, response_text)
                            logger.info("Successfully sent response to server")
                        except Exception as e:
                            logger.error(f"Error sending response to server: {e}", exc_info=True)
                    else:
                        logger.warning("No session ID available, cannot send to server")
                    
                    # Return the updated history and clear response options
                    return history, session_id_text.value, []
                except Exception as e:
                    logger.error(f"Error in handle_btn2_click: {e}", exc_info=True)
                    return text_chatbot.value, session_id_text.value, []
            
            @log_function_call
            def handle_btn3_click(response_value):
                try:
                    logger.info(f"Button 3 clicked - incoming value: '{response_value}'")
                    
                    if not response_value:
                        logger.warning("Button 3 has no value")
                        return text_chatbot.value, session_id_text.value, []
                    
                    response_text = response_value.split(". ", 1)[1] if ". " in response_value else response_value
                    logger.info(f"選擇回應按鈕3: {response_text}")
                    
                    # Update the chat history directly
                    history = text_chatbot.value.copy() if text_chatbot.value else []
                    
                    # 找到最近一次用户输入的内容
                    last_user_input = "你好"  # 默认值
                    if history:
                        for i in range(len(history)-1, -1, -1):
                            if history[i][0]:  # 如果用户输入不为空
                                last_user_input = history[i][0]
                                break
                    
                    if history and history[-1][1] is None:
                        history[-1][1] = response_text
                        logger.info(f"更新對話歷史: {history}")
                    elif history:
                        logger.info(f"Adding new entry to history with last user input: {last_user_input}")
                        history.append([last_user_input, response_text])
                    else:
                        history = [[last_user_input, response_text]]
                    
                    # Force update the chatbot directly
                    text_chatbot.value = history
                    
                    # Try to send the selected response to the server
                    if session_id_text.value:
                        try:
                            logger.info(f"Sending response to server: {response_text}")
                            self.api_client.update_selected_response(session_id_text.value, response_text)
                            logger.info("Successfully sent response to server")
                        except Exception as e:
                            logger.error(f"Error sending response to server: {e}", exc_info=True)
                    else:
                        logger.warning("No session ID available, cannot send to server")
                    
                    return history, session_id_text.value, []
                except Exception as e:
                    logger.error(f"Error in handle_btn3_click: {e}", exc_info=True)
                    return text_chatbot.value, session_id_text.value, []
            
            @log_function_call
            def handle_btn4_click(response_value):
                try:
                    logger.info(f"Button 4 clicked - incoming value: '{response_value}'")
                    
                    if not response_value:
                        logger.warning("Button 4 has no value")
                        return text_chatbot.value, session_id_text.value, []
                    
                    response_text = response_value.split(". ", 1)[1] if ". " in response_value else response_value
                    logger.info(f"選擇回應按鈕4: {response_text}")
                    
                    # Update the chat history directly
                    history = text_chatbot.value.copy() if text_chatbot.value else []
                    
                    # 找到最近一次用户输入的内容
                    last_user_input = "你好"  # 默认值
                    if history:
                        for i in range(len(history)-1, -1, -1):
                            if history[i][0]:  # 如果用户输入不为空
                                last_user_input = history[i][0]
                                break
                    
                    if history and history[-1][1] is None:
                        history[-1][1] = response_text
                        logger.info(f"更新對話歷史: {history}")
                    elif history:
                        logger.info(f"Adding new entry to history with last user input: {last_user_input}")
                        history.append([last_user_input, response_text])
                    else:
                        history = [[last_user_input, response_text]]
                    
                    # Force update the chatbot directly
                    text_chatbot.value = history
                    
                    # Try to send the selected response to the server
                    if session_id_text.value:
                        try:
                            logger.info(f"Sending response to server: {response_text}")
                            self.api_client.update_selected_response(session_id_text.value, response_text)
                            logger.info("Successfully sent response to server")
                        except Exception as e:
                            logger.error(f"Error sending response to server: {e}", exc_info=True)
                    else:
                        logger.warning("No session ID available, cannot send to server")
                    
                    return history, session_id_text.value, []
                except Exception as e:
                    logger.error(f"Error in handle_btn4_click: {e}", exc_info=True)
                    return text_chatbot.value, session_id_text.value, []
            
            @log_function_call
            def handle_btn5_click(response_value):
                try:
                    logger.info(f"Button 5 clicked - incoming value: '{response_value}'")
                    
                    if not response_value:
                        logger.warning("Button 5 has no value")
                        return text_chatbot.value, session_id_text.value, []
                    
                    response_text = response_value.split(". ", 1)[1] if ". " in response_value else response_value
                    logger.info(f"選擇回應按鈕5: {response_text}")
                    
                    # Update the chat history directly
                    history = text_chatbot.value.copy() if text_chatbot.value else []
                    
                    # 找到最近一次用户输入的内容
                    last_user_input = "你好"  # 默认值
                    if history:
                        for i in range(len(history)-1, -1, -1):
                            if history[i][0]:  # 如果用户输入不为空
                                last_user_input = history[i][0]
                                break
                    
                    if history and history[-1][1] is None:
                        history[-1][1] = response_text
                        logger.info(f"更新對話歷史: {history}")
                    elif history:
                        logger.info(f"Adding new entry to history with last user input: {last_user_input}")
                        history.append([last_user_input, response_text])
                    else:
                        history = [[last_user_input, response_text]]
                    
                    # Force update the chatbot directly
                    text_chatbot.value = history
                    
                    # Try to send the selected response to the server
                    if session_id_text.value:
                        try:
                            logger.info(f"Sending response to server: {response_text}")
                            self.api_client.update_selected_response(session_id_text.value, response_text)
                            logger.info("Successfully sent response to server")
                        except Exception as e:
                            logger.error(f"Error sending response to server: {e}", exc_info=True)
                    else:
                        logger.warning("No session ID available, cannot send to server")
                    
                    return history, session_id_text.value, []
                except Exception as e:
                    logger.error(f"Error in handle_btn5_click: {e}", exc_info=True)
                    return text_chatbot.value, session_id_text.value, []
            
            # 設置按鈕點擊事件 - 传入按钮本身的值
            response_btn1.click(
                fn=handle_btn1_click,
                inputs=[response_btn1],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=lambda: gr.update(visible=False),
                inputs=[],
                outputs=[response_box]
            )
            
            # 設置其他按鈕點擊事件
            response_btn2.click(
                fn=handle_btn2_click,
                inputs=[response_btn2],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=lambda: gr.update(visible=False),
                inputs=[],
                outputs=[response_box]
            )
            
            response_btn3.click(
                fn=handle_btn3_click,
                inputs=[response_btn3],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=lambda: gr.update(visible=False),
                inputs=[],
                outputs=[response_box]
            )
            
            response_btn4.click(
                fn=handle_btn4_click,
                inputs=[response_btn4],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=lambda: gr.update(visible=False),
                inputs=[],
                outputs=[response_box]
            )
            
            response_btn5.click(
                fn=handle_btn5_click,
                inputs=[response_btn5],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=lambda: gr.update(visible=False),
                inputs=[],
                outputs=[response_box]
            )
            
            # 監聽回應選項變化，更新按鈕
            response_options.change(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            )
            
            # 設置文本對話事件處理
            text_send_btn.click(
                fn=handle_text_input,
                inputs=[text_input, text_chatbot, character_id, session_id_text, custom_config],
                outputs=[text_input, text_chatbot, session_id_text, response_options]
            )
            
            text_input.submit(
                fn=handle_text_input,
                inputs=[text_input, text_chatbot, character_id, session_id_text, custom_config],
                outputs=[text_input, text_chatbot, session_id_text, response_options]
            )
            
            text_reset_btn.click(
                fn=handle_reset_text,
                inputs=[],
                outputs=[text_chatbot, session_id_text, response_options]
            )
            
            # 更新文本對話角色選擇
            text_selector.change(
                fn=update_text_character,
                inputs=[
                    text_selector,
                    text_custom_char["use_custom_config"],
                    text_custom_char["name"],
                    text_custom_char["persona"],
                    text_custom_char["backstory"],
                    text_custom_char["goal"],
                    text_custom_char["fixed_settings"],
                    text_custom_char["floating_settings"]
                ],
                outputs=[character_id, session_id_text, custom_config]
            )
            
            # 當自定義配置變更時重新生成配置
            text_custom_char["use_custom_config"].change(
                fn=update_text_character,
                inputs=[
                    text_selector,
                    text_custom_char["use_custom_config"],
                    text_custom_char["name"],
                    text_custom_char["persona"],
                    text_custom_char["backstory"],
                    text_custom_char["goal"],
                    text_custom_char["fixed_settings"],
                    text_custom_char["floating_settings"]
                ],
                outputs=[character_id, session_id_text, custom_config]
            )
            
            # 設置語音對話事件處理
            audio_input.stop(
                fn=handle_audio_input,
                inputs=[audio_input, audio_chatbot, character_id, session_id_audio, custom_config],
                outputs=[audio_chatbot, session_id_audio]
            )
            
            audio_reset_btn.click(
                fn=handle_reset_audio,
                inputs=[],
                outputs=[audio_chatbot, session_id_audio]
            )
            
            # 更新語音對話角色選擇
            audio_selector.change(
                fn=update_audio_character,
                inputs=[
                    audio_selector,
                    audio_custom_char["use_custom_config"],
                    audio_custom_char["name"],
                    audio_custom_char["persona"],
                    audio_custom_char["backstory"],
                    audio_custom_char["goal"],
                    audio_custom_char["fixed_settings"],
                    audio_custom_char["floating_settings"]
                ],
                outputs=[character_id, session_id_audio, custom_config]
            )
            
            # 當自定義配置變更時重新生成配置
            audio_custom_char["use_custom_config"].change(
                fn=update_audio_character,
                inputs=[
                    audio_selector,
                    audio_custom_char["use_custom_config"],
                    audio_custom_char["name"],
                    audio_custom_char["persona"],
                    audio_custom_char["backstory"],
                    audio_custom_char["goal"],
                    audio_custom_char["fixed_settings"],
                    audio_custom_char["floating_settings"]
                ],
                outputs=[character_id, session_id_audio, custom_config]
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
            
            # Add debug function for UI state
            @log_function_call
            def debug_component_states():
                """Debug function to print the current states of components"""
                logger.info("=== DEBUG COMPONENT STATES ===")
                logger.info(f"Response Box visible: {response_box.visible}")
                logger.info(f"Button 1: visible={response_btn1.visible}, value='{response_btn1.value}'")
                logger.info(f"Button 2: visible={response_btn2.visible}, value='{response_btn2.value}'")
                logger.info(f"Button 3: visible={response_btn3.visible}, value='{response_btn3.value}'") 
                logger.info(f"Button 4: visible={response_btn4.visible}, value='{response_btn4.value}'")
                logger.info(f"Button 5: visible={response_btn5.visible}, value='{response_btn5.value}'")
                logger.info(f"Current chatbot history: {text_chatbot.value}")
                logger.info(f"Current session ID: {session_id_text.value}")
                logger.info("=== END DEBUG ===")
                return None
                
            # Add debug button for development (hidden in production)
            debug_button = gr.Button("Debug State", visible=True)
            debug_button.click(fn=debug_component_states, inputs=[], outputs=[])
        
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
            "audio_reset_btn": audio_reset_btn,
            "text_custom_char": text_custom_char,
            "audio_custom_char": audio_custom_char
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