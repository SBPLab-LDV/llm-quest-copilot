import gradio as gr
import os
import tempfile
import time
import json
import logging
import sys
import inspect
import codecs
import io
from typing import List, Dict, Any, Tuple, Optional

from .client import ApiClient
from .components import create_character_selector, create_response_format_selector, create_dialogue_interface, create_custom_character_interface

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
log_file_path = os.path.join(project_root, 'ui_debug.log')

# 自定義 StreamHandler 來處理 Windows 控制台編碼問題
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # 安全輸出，捕獲任何編碼錯誤
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                # 對於 Windows 控制台，移除不能顯示的字符或使用替代字符
                safe_msg = "".join(c if ord(c) < 128 else '?' for c in msg)
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# 設置日誌記錄，修改為支持 UTF-8 編碼
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # 只使用文件處理器，避免控制台輸出的編碼問題
        logging.FileHandler(log_file_path, mode='w', encoding='utf-8')  # 使用 utf-8 編碼
    ]
)

# 添加安全控制台處理器
console_handler = SafeStreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# 獲取根日誌記錄器並添加處理器
root_logger = logging.getLogger()
root_logger.addHandler(console_handler)

# 應用模組日誌記錄器
logger = logging.getLogger(__name__)

# Log some debug info at startup
logger.info(f"Starting UI application")
logger.info(f"Log file path: {log_file_path}")
logger.info(f"Current directory: {current_dir}")
logger.info(f"Project root: {project_root}")
logger.info(f"System encoding: {sys.stdout.encoding}")

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
    
    def __init__(self, api_url: str = "http://0.0.0.0:8000"):
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
        with gr.Blocks(
            theme=gr.themes.Soft(), 
            title="醫護對話系統 v0.3.2",
            css="""
            #response_box, #audio_response_box {
                border: 1px solid rgba(128, 128, 128, 0.2) !important; 
                border-radius: 8px !important;
                padding: 10px !important;
                margin-top: 15px !important;
                background-color: rgba(247, 247, 248, 0.7) !important;
            }
            #response_box button, #audio_response_box button {
                margin: 5px !important;
                text-align: left !important;
            }
            """
        ) as app:
            gr.Markdown("# 醫護對話系統 v0.3.2")
            gr.Markdown("使用此界面與虛擬病患進行對話。您可以選擇不同的角色進行對話。")
            
            # 創建會話狀態（預設為第一個正式角色：王大華）
            character_id = gr.State("1")
            session_id_text = gr.State(None)  # 文本對話會話 ID
            session_id_audio = gr.State(None)  # 語音對話會話 ID
            custom_config = gr.State(None)  # 自定義角色配置
            
            # 使用標籤頁創建兩種不同的界面
            with gr.Tabs() as tabs:
                # 文字回答標籤頁
                with gr.TabItem("文字回答"):
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
                with gr.TabItem("口語表達"):
                    with gr.Row():
                        with gr.Column(scale=3):
                            # 創建聊天區
                            audio_chatbot = gr.Chatbot(label="對話歷史", height=500)
                            
                            # 添加回應選項區域 - 確保它在語音對話標籤中
                            with gr.Column(visible=False, elem_id="audio_response_box") as audio_response_box:
                                gr.Markdown("### 請選擇您想表達的內容")
                                
                                # 建立5個按鈕用於語音選項
                                audio_btn1 = gr.Button("選項1", visible=False, variant="primary")
                                audio_btn2 = gr.Button("選項2", visible=False, variant="primary")
                                audio_btn3 = gr.Button("選項3", visible=False, variant="primary")
                                audio_btn4 = gr.Button("選項4", visible=False, variant="primary")
                                audio_btn5 = gr.Button("選項5", visible=False, variant="primary")
                            
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
                
                # 強制更新response_box可見性
                response_box.visible = True
                response_buttons_container.visible = True
                
                # 建立按鈕更新字典 - 只包含正確的輸出組件
                updates = {
                    response_box: gr.update(visible=True)
                }
                buttons = [response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
                
                # 更新所有按鈕
                for i, button in enumerate(buttons):
                    if i < len(response_list) and response_list[i]:
                        option_text = response_list[i]
                        # 檢查是否為 JSON 字符串，嘗試提取內部選項
                        try:
                            if isinstance(option_text, str) and (option_text.startswith('{') or option_text.startswith('```')):
                                # 嘗試清理并解析可能的 JSON 字符串
                                cleaned_text = option_text
                                if cleaned_text.startswith('```json'):
                                    cleaned_text = cleaned_text[7:]
                                if cleaned_text.endswith('```'):
                                    cleaned_text = cleaned_text[:-3]
                                cleaned_text = cleaned_text.strip()
                                
                                # 嘗試解析為 JSON
                                if cleaned_text.startswith('{'):
                                    json_data = json.loads(cleaned_text)
                                    if 'options' in json_data and isinstance(json_data['options'], list) and json_data['options']:
                                        # 使用 JSON 中的選項而不是整個 JSON 字符串
                                        option_text = json_data['options'][i] if i < len(json_data['options']) else option_text
                                        logger.info(f"從 JSON 中提取選項 {i+1}: {option_text}")
                        except Exception as e:
                            logger.warning(f"解析選項時出錯: {e}")
                            # 繼續使用原始文本
                        
                        button_text = f"{i+1}. {option_text}"
                        logger.info(f"設置按鈕 {i+1} 文字: {button_text}")
                        # 直接修改按鈕屬性並強制可見性
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
            
            def handle_response_btn_click(option_text, history, session_id):
                """處理文本對話按鈕點擊"""
                # 移除編號前綴
                if ". " in option_text:
                    option_text = option_text.split(". ", 1)[1]
                
                logger.info(f"用戶點擊回應按鈕: {option_text}")
                
                # 在聊天歷史中，修改現有的上一條消息
                # 確保虛擬病患的回應顯示在左側（白色框）而非右側（藍色框）
                if history and len(history) > 0 and history[-1][1] is None:
                    # 更新最後一個對話的回應部分
                    history[-1][1] = option_text
                else:
                    # 如果沒有待回應的消息，則添加新的病患回應
                    history = history + [["", option_text]]
                
                # 發送選擇給伺服器，但不要將其作為新消息處理
                try:
                    # 只記錄選擇，不要處理返回的回應
                    self.api_client.update_selected_response(session_id, option_text)
                    # 明確不添加伺服器返回的回應到對話歷史中
                except Exception as e:
                    logger.error(f"記錄選擇時出錯: {e}")
                
                # 返回更新後的對話歷史和會話ID，清空選項
                return history, session_id, []

            @log_function_call
            def _clear_text_input():
                """在選擇回覆後清空文字輸入，避免誤將病患回覆當成下一輪提問送出"""
                return ""
            
            @log_function_call
            def handle_text_input(text, history, char_id, sess_id, config):
                """處理文本輸入"""
                if not text.strip():
                    return "", history, sess_id, []
                
                logger.info(f"開始處理文本輸入，現有會話ID: {sess_id}")
                logger.info(f"角色ID: {char_id}")
                logger.info(f"配置: {config is not None}")
                
                # 更新 API 客戶端設置 - 但不要重置会话ID
                if self.api_client.character_id != char_id or self.api_client.character_config != config:
                    logger.info(f"角色已變更，設置新角色但保留現有會話ID")
                    # 保存现有会话ID
                    current_session_id = self.api_client.session_id
                    # 设置新角色
                    if config:
                        logger.info(f"使用自定義配置，角色ID: {char_id}")
                        self.api_client.set_character(char_id, config)
                    else:
                        logger.info(f"使用預設角色ID: {char_id}")
                        self.api_client.set_character(char_id)
                    # 恢复会话ID
                    if current_session_id or sess_id:
                        self.api_client.session_id = current_session_id or sess_id
                        logger.info(f"恢復會話ID: {self.api_client.session_id}")
                
                # 确保会话ID一致
                if sess_id and self.api_client.session_id != sess_id:
                    logger.info(f"同步客户端会话ID: 從{self.api_client.session_id}到{sess_id}")
                    self.api_client.session_id = sess_id
                
                # 检查是否在选择语音识别选项 (输入为数字1-5)
                if text.isdigit() and 1 <= int(text) <= 5 and response_options.value and len(response_options.value) >= int(text):
                    option_index = int(text) - 1
                    selected_option = response_options.value[option_index]
                    logger.info(f"用户选择了选项 {text}: {selected_option}")
                    
                    # 添加选项作为用户输入
                    history = history + [[selected_option, None]]
                    
                    # 发送选择到服务器
                    try:
                        response = self.api_client.update_selected_response(self.api_client.session_id, selected_option)
                        if "responses" in response and response["responses"]:
                            history[-1][1] = response["responses"][0]
                        if "session_id" in response:
                            sess_id = response["session_id"]
                            self.api_client.session_id = sess_id
                    except Exception as e:
                        logger.error(f"发送选择到服务器时出错: {e}")
                        history[-1][1] = "处理您的选择时出错。"
                    
                    # 清空选项
                    return "", history, sess_id, []
                
                # 添加用戶輸入到聊天歷史
                history = history + [[text, None]]
                
                # 直接更新chatbot UI
                text_chatbot.value = history
                
                # 準備請求數據
                request_data = {
                    "text": text,
                    "response_format": "text"
                }
                
                # 根據是否有自定義配置決定使用哪種方式
                if config:
                    logger.info("使用自定義角色配置發送請求")
                    request_data["character_config"] = config
                    # 記錄主要配置內容
                    if isinstance(config, dict):
                        logger.debug(f"配置鍵: {list(config.keys())}")
                        if "details" in config:
                            logger.debug(f"固定設定鍵: {list(config.get('details', {}).get('fixed_settings', {}).keys())}")
                            logger.debug(f"浮動設定鍵: {list(config.get('details', {}).get('floating_settings', {}).keys())}")
                else:
                    logger.info(f"使用預設角色ID: {char_id}")
                    request_data["character_id"] = char_id
                
                # 如果有會話ID，添加到請求中
                if sess_id:
                    request_data["session_id"] = sess_id
                    logger.info(f"使用現有會話ID: {sess_id}")
                
                # 發送請求
                logger.info(f"發送文本: {text}")
                response = self.api_client.send_text(request_data)
                logger.info(f"收到回應: {response}")
                
                # 處理文本回應
                if "responses" in response and response["responses"]:
                    # 更新會話 ID
                    if "session_id" in response:
                        sess_id = response["session_id"]
                        self.api_client.session_id = sess_id  # 确保同步客户端的会话ID
                        logger.info(f"更新會話ID: {sess_id}")
                        
                        # 重要：让所有组件更新会话ID
                        session_id_text.value = sess_id
                    
                    # 記錄對話歷史和會話ID供除錯用途
                    logger.info(f"當前完整對話歷史: {history}")
                    logger.info(f"API客戶端會話ID: {self.api_client.session_id}")
                    # 若伺服器提供會話專屬日誌路徑，保存到狀態供 Log Viewer 使用
                    try:
                        logs_field = response.get("logs") if isinstance(response, dict) else None
                        if logs_field and isinstance(logs_field, dict):
                            chat_log_path = logs_field.get("chat_gui")
                            if chat_log_path:
                                logger.info(f"更新 Log Viewer 路徑: {chat_log_path}")
                                log_path_state.value = chat_log_path
                    except Exception:
                        pass
                    
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
                    history[-1][1] = "發生錯誤，無法獲取回應。"
                    text_chatbot.value = history  # 更新UI显示错误信息
                    # 隱藏回應選項
                    return "", history, sess_id, []
            
            def handle_reset_text():
                """重置文本對話"""
                self.api_client.reset_session()
                # 清空每會話日誌覆寫路徑，避免刷新時讀取舊檔
                try:
                    log_path_state.value = None
                except Exception:
                    pass
                return [], None, []
            
            def handle_reset_audio():
                """重置語音對話"""
                self.api_client.reset_session()
                # 清空每會話日誌覆寫路徑，避免刷新時讀取舊檔
                try:
                    log_path_state.value = None
                except Exception:
                    pass
                return [], None, []
            
            def handle_audio_input(audio_path, history, char_id, sess_id, config):
                """處理音頻輸入"""
                if not audio_path:
                    return history, sess_id, []
                
                logger.info(f"處理音頻輸入: {audio_path}")
                logger.info(f"當前角色ID: {char_id}")
                logger.info(f"當前會話ID: {sess_id}")
                logger.info(f"自定義配置: {config}")
                
                # 準備請求數據
                request_data = {
                    "audio_file": audio_path,
                    "response_format": "text"
                }
                
                # 根據是否有自定義配置決定使用哪種方式
                if config:
                    logger.info("使用自定義角色配置")
                    request_data["character_config"] = config
                else:
                    logger.info(f"使用預設角色ID: {char_id}")
                    request_data["character_id"] = char_id
                
                # 如果有會話ID，添加到請求中
                if sess_id:
                    request_data["session_id"] = sess_id
                
                # 添加用戶輸入到聊天歷史
                history = history + [["[語音輸入]", None]]
                
                # 發送請求
                response = self.api_client.send_audio(request_data)
                logger.debug(f"音頻識別回應: {response}")
                
                # 檢查回應中是否包含語音識別選項
                if "speech_recognition_options" in response and response["speech_recognition_options"]:
                    # 直接從回應中獲取語音識別選項
                    options = response["speech_recognition_options"]
                    logger.info(f"收到語音識別選項: {options}")
                    
                    # 更新會話 ID
                    if "session_id" in response:
                        sess_id = response["session_id"]
                        
                    # 顯示提示訊息作為對話系統的回應
                    if "responses" in response and response["responses"]:
                        prompt = response["responses"][0]
                        history[-1][1] = prompt
                    else:
                        history[-1][1] = "請從以下選項中選擇您想表達的內容:"
                    
                    # 儲存伺服器提供的每會話日誌路徑（若有）
                    try:
                        logs_field = response.get("logs") if isinstance(response, dict) else None
                        if logs_field and isinstance(logs_field, dict):
                            chat_log_path = logs_field.get("chat_gui")
                            if chat_log_path:
                                logger.info(f"更新 Log Viewer 路徑(音頻): {chat_log_path}")
                                log_path_state.value = chat_log_path
                    except Exception:
                        pass
                    # 返回選項列表給按鈕更新函數
                    return history, sess_id, options
                else:
                    # 如果沒有選項，處理普通回應
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
                    
                    # 儲存伺服器提供的每會話日誌路徑（若有）
                    try:
                        logs_field = response.get("logs") if isinstance(response, dict) else None
                        if logs_field and isinstance(logs_field, dict):
                            chat_log_path = logs_field.get("chat_gui")
                            if chat_log_path:
                                logger.info(f"更新 Log Viewer 路徑(音頻一般): {chat_log_path}")
                                log_path_state.value = chat_log_path
                    except Exception:
                        pass
                    # 沒有選項時返回空選項列表
                    return history, sess_id, []
                    
            # 處理語音選項按鈕點擊
            def handle_audio_option_click(option_text, history, session_id):
                """處理按鈕點擊選擇語音選項"""
                # 移除編號前綴
                if ". " in option_text:
                    option_text = option_text.split(". ", 1)[1]
                
                logger.info(f"用戶選擇了語音選項: {option_text}")
                
                # 添加用戶選擇到對話歷史
                history = history + [[option_text, None]]
                
                # 發送選擇給伺服器
                try:
                    response = self.api_client.update_selected_response(session_id, option_text)
                    
                    if response and "responses" in response and response["responses"]:
                        # 添加回應
                        history[-1][1] = response["responses"][0]
                        
                    # 更新會話ID
                    if response and "session_id" in response:
                        session_id = response["session_id"]
                except Exception as e:
                    logger.error(f"處理選擇時出錯: {e}")
                    history[-1][1] = "處理您的選擇時出錯。"
                
                # 返回更新後的對話歷史和會話ID，清空選項
                return history, session_id, []
                
            # 更新語音按鈕顯示
            @log_function_call
            def update_audio_buttons(options):
                """更新語音選項按鈕顯示"""
                logger.info(f"更新語音按鈕顯示: {options}")
                
                if not options or len(options) == 0:
                    logger.info("沒有語音選項，隱藏所有按鈕")
                    # 直接更新組件可見性
                    audio_response_box.visible = False
                    audio_btn1.visible = False
                    audio_btn2.visible = False
                    audio_btn3.visible = False
                    audio_btn4.visible = False
                    audio_btn5.visible = False
                    
                    # 返回更新
                    return [
                        gr.update(visible=False),
                        gr.update(visible=False, value="選項1"),
                        gr.update(visible=False, value="選項2"),
                        gr.update(visible=False, value="選項3"),
                        gr.update(visible=False, value="選項4"),
                        gr.update(visible=False, value="選項5")
                    ]
                
                logger.info(f"顯示 {len(options)} 個語音選項按鈕")
                
                # 強制更新容器可見性
                audio_response_box.visible = True
                
                # 顯示選項按鈕
                updates = [gr.update(visible=True)]
                
                # 更新每個按鈕
                for i in range(5):
                    if i < len(options):
                        btn_text = f"{i+1}. {options[i]}"
                        updates.append(gr.update(visible=True, value=btn_text))
                        
                        # 直接設置按鈕可見性和文字
                        if i == 0:
                            audio_btn1.visible = True
                            audio_btn1.value = btn_text
                        elif i == 1:
                            audio_btn2.visible = True
                            audio_btn2.value = btn_text
                        elif i == 2:
                            audio_btn3.visible = True
                            audio_btn3.value = btn_text
                        elif i == 3:
                            audio_btn4.visible = True
                            audio_btn4.value = btn_text
                        elif i == 4:
                            audio_btn5.visible = True
                            audio_btn5.value = btn_text
                    else:
                        updates.append(gr.update(visible=False, value=f"選項{i+1}"))
                        
                        # 直接隱藏不需要的按鈕
                        if i == 0:
                            audio_btn1.visible = False
                        elif i == 1:
                            audio_btn2.visible = False
                        elif i == 2:
                            audio_btn3.visible = False
                        elif i == 3:
                            audio_btn4.visible = False
                        elif i == 4:
                            audio_btn5.visible = False
                
                return updates
            
            def update_text_character(char_name, use_custom, name, persona, backstory, goal, fixed, floating):
                """更新文本對話角色選擇"""
                logger.info(f"更新文本對話角色: {char_name}")
                logger.info(f"使用自定義角色: {use_custom}")
                
                if use_custom:
                    # 使用自定義角色配置
                    logger.info("生成自定義角色配置")
                    logger.info(f"名稱: {name}")
                    logger.info(f"個性 (簡略): {persona[:20]}...")
                    logger.info(f"背景 (簡略): {backstory[:20]}...")
                    logger.info(f"目標 (簡略): {goal[:20]}...")
                    
                    config_fn = text_custom_char["generate_config"]
                    config = config_fn(use_custom, name, persona, backstory, goal, fixed, floating)
                    
                    # 檢查配置是否有效
                    if config and "error" not in config:
                        # 使用隨機 ID 作為自定義角色 ID
                        custom_id = f"custom_{int(time.time())}"
                        logger.info(f"生成的自定義角色ID: {custom_id}")
                        
                        # 記錄配置結構
                        if isinstance(config, dict):
                            logger.info(f"配置包含以下鍵: {list(config.keys())}")
                            if "details" in config:
                                logger.info(f"固定設定: {config.get('details', {}).get('fixed_settings', {})}")
                                logger.info(f"浮動設定: {config.get('details', {}).get('floating_settings', {})}")
                        
                        self.api_client.set_character(custom_id, config)
                        logger.info(f"已設置自定義角色，ID: {custom_id}")
                        
                        # 重置會話ID，確保新對話使用新的角色設定
                        sess_id = None
                        self.api_client.reset_session()
                        logger.info("已重置會話ID以使用新的角色設定")
                        # 清空每會話日誌覆寫路徑，避免刷新時讀取舊檔
                        try:
                            log_path_state.value = None
                        except Exception:
                            pass
                        
                        return custom_id, sess_id, config
                    else:
                        # 配置錯誤，使用默認角色
                        logger.error(f"自定義角色配置無效，使用默認角色")
                        char_id = text_character_map.get(char_name, "1")
                        self.api_client.set_character(char_id)
                        
                        # 重置會話ID
                        sess_id = None
                        self.api_client.reset_session()
                        # 清空每會話日誌覆寫路徑
                        try:
                            log_path_state.value = None
                        except Exception:
                            pass
                        
                        return char_id, sess_id, None
                else:
                    # 使用預設角色
                    logger.info(f"使用預設角色名稱: {char_name}")
                    char_id = text_character_map.get(char_name, "1")
                    logger.info(f"預設角色ID: {char_id}")
                    self.api_client.set_character(char_id)
                    
                    # 重置會話ID
                    sess_id = None
                    self.api_client.reset_session()
                    logger.info("已重置會話ID以使用新的角色設定")
                    # 清空每會話日誌覆寫路徑
                    try:
                        log_path_state.value = None
                    except Exception:
                        pass
                    
                    return char_id, sess_id, None
            
            def update_audio_character(char_name, use_custom, name, persona, backstory, goal, fixed, floating):
                """更新語音對話角色選擇"""
                logger.info(f"更新語音對話角色: {char_name}")
                logger.info(f"使用自定義角色: {use_custom}")
                
                if use_custom:
                    # 使用自定義角色配置
                    logger.info("生成自定義角色配置")
                    logger.info(f"名稱: {name}")
                    logger.info(f"個性 (簡略): {persona[:20]}...")
                    logger.info(f"背景 (簡略): {backstory[:20]}...")
                    logger.info(f"目標 (簡略): {goal[:20]}...")
                    
                    config_fn = audio_custom_char["generate_config"]
                    config = config_fn(use_custom, name, persona, backstory, goal, fixed, floating)
                    
                    # 檢查配置是否有效
                    if config and "error" not in config:
                        # 使用隨機 ID 作為自定義角色 ID
                        custom_id = f"custom_{int(time.time())}"
                        logger.info(f"生成的自定義角色ID: {custom_id}")
                        
                        # 記錄配置結構
                        if isinstance(config, dict):
                            logger.info(f"配置包含以下鍵: {list(config.keys())}")
                            if "details" in config:
                                logger.info(f"固定設定: {config.get('details', {}).get('fixed_settings', {})}")
                                logger.info(f"浮動設定: {config.get('details', {}).get('floating_settings', {})}")
                        
                        self.api_client.set_character(custom_id, config)
                        logger.info(f"已設置自定義角色，ID: {custom_id}")
                        
                        # 重置會話ID，確保新對話使用新的角色設定
                        sess_id = None
                        self.api_client.reset_session()
                        logger.info("已重置會話ID以使用新的角色設定")
                        # 清空每會話日誌覆寫路徑
                        try:
                            log_path_state.value = None
                        except Exception:
                            pass
                        
                        return custom_id, sess_id, config
                    else:
                        # 配置錯誤，使用默認角色
                        logger.error(f"自定義角色配置無效，使用默認角色")
                        char_id = audio_character_map.get(char_name, "1")
                        self.api_client.set_character(char_id)
                        
                        # 重置會話ID
                        sess_id = None
                        self.api_client.reset_session()
                        # 清空每會話日誌覆寫路徑
                        try:
                            log_path_state.value = None
                        except Exception:
                            pass
                        
                        return char_id, sess_id, None
                else:
                    # 使用預設角色
                    logger.info(f"使用預設角色名稱: {char_name}")
                    char_id = audio_character_map.get(char_name, "1")
                    logger.info(f"預設角色ID: {char_id}")
                    self.api_client.set_character(char_id)
                    
                    # 重置會話ID
                    sess_id = None
                    self.api_client.reset_session()
                    logger.info("已重置會話ID以使用新的角色設定")
                    # 清空每會話日誌覆寫路徑
                    try:
                        log_path_state.value = None
                    except Exception:
                        pass
                    
                    return char_id, sess_id, None
            
            # 設置語音對話事件處理
            audio_input.stop(
                fn=handle_audio_input,
                inputs=[audio_input, audio_chatbot, character_id, session_id_audio, custom_config],
                outputs=[audio_chatbot, session_id_audio, response_options]
            ).then(
                fn=update_audio_buttons,
                inputs=[response_options],
                outputs=[audio_response_box, audio_btn1, audio_btn2, audio_btn3, audio_btn4, audio_btn5]
            )
            
            # 定義一個專門用於隱藏選項的函數
            @log_function_call
            def hide_audio_options():
                """隱藏所有音頻選項按鈕"""
                logger.info("隱藏所有音頻選項按鈕")
                # 直接更新組件可見性
                audio_response_box.visible = False
                audio_btn1.visible = False
                audio_btn2.visible = False
                audio_btn3.visible = False
                audio_btn4.visible = False
                audio_btn5.visible = False
                
                # 返回更新字典格式
                return [
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False)
                ]
            
            # 設置語音選項按鈕點擊事件
            audio_btn1.click(
                fn=handle_audio_option_click,
                inputs=[audio_btn1, audio_chatbot, session_id_audio],
                outputs=[audio_chatbot, session_id_audio, response_options]
            ).then(
                fn=hide_audio_options,
                outputs=[audio_response_box, audio_btn1, audio_btn2, audio_btn3, audio_btn4, audio_btn5]
            )
            
            audio_btn2.click(
                fn=handle_audio_option_click,
                inputs=[audio_btn2, audio_chatbot, session_id_audio],
                outputs=[audio_chatbot, session_id_audio, response_options]
            ).then(
                fn=hide_audio_options,
                outputs=[audio_response_box, audio_btn1, audio_btn2, audio_btn3, audio_btn4, audio_btn5]
            )
            
            audio_btn3.click(
                fn=handle_audio_option_click,
                inputs=[audio_btn3, audio_chatbot, session_id_audio],
                outputs=[audio_chatbot, session_id_audio, response_options]
            ).then(
                fn=hide_audio_options,
                outputs=[audio_response_box, audio_btn1, audio_btn2, audio_btn3, audio_btn4, audio_btn5]
            )
            
            audio_btn4.click(
                fn=handle_audio_option_click,
                inputs=[audio_btn4, audio_chatbot, session_id_audio],
                outputs=[audio_chatbot, session_id_audio, response_options]
            ).then(
                fn=hide_audio_options,
                outputs=[audio_response_box, audio_btn1, audio_btn2, audio_btn3, audio_btn4, audio_btn5]
            )
            
            audio_btn5.click(
                fn=handle_audio_option_click,
                inputs=[audio_btn5, audio_chatbot, session_id_audio],
                outputs=[audio_chatbot, session_id_audio, response_options]
            ).then(
                fn=hide_audio_options,
                outputs=[audio_response_box, audio_btn1, audio_btn2, audio_btn3, audio_btn4, audio_btn5]
            )
            
            audio_reset_btn.click(
                fn=handle_reset_audio,
                inputs=[],
                outputs=[audio_chatbot, session_id_audio, response_options]
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
            
            # 設置文本對話事件處理
            text_send_btn.click(
                fn=handle_text_input,
                inputs=[text_input, text_chatbot, character_id, session_id_text, custom_config],
                outputs=[text_input, text_chatbot, session_id_text, response_options]
            ).then(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            )
            
            text_input.submit(
                fn=handle_text_input,
                inputs=[text_input, text_chatbot, character_id, session_id_text, custom_config],
                outputs=[text_input, text_chatbot, session_id_text, response_options]
            ).then(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            )
            
            text_reset_btn.click(
                fn=handle_reset_text,
                inputs=[],
                outputs=[text_chatbot, session_id_text, response_options]
            )
            
            # 設置文本對話的角色選擇事件處理
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
            
            # 當文本對話自定義配置變更時重新生成配置
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
            
            # 當自定義配置的字段發生變化時，更新配置
            for field in ["name", "persona", "backstory", "goal", "fixed_settings", "floating_settings"]:
                if field in text_custom_char:
                    text_custom_char[field].change(
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
            
            # 當自定義配置的字段發生變化時，更新配置
            for field in ["name", "persona", "backstory", "goal", "fixed_settings", "floating_settings"]:
                if field in audio_custom_char:
                    audio_custom_char[field].change(
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
                
            # Debug State 與 新會話按鈕已移除（改以瀏覽器重新整理啟動新會話）

            # ------------------------
            # Log Viewer (local files)
            # ------------------------
            with gr.Accordion("對話紀錄 (Log Viewer)", open=False):
                log_info = gr.Markdown("載入最近的對話紀錄檔案（本地 logs/api）")
                with gr.Row():
                    log_limit = gr.Slider(minimum=10, maximum=200, step=10, value=50, label="顯示筆數")
                    log_mask = gr.Checkbox(label="遮蔽敏感資訊 (試驗)", value=False)
                with gr.Row():
                    current_session_display = gr.Textbox(label="目前會話ID", interactive=False)
                    current_character_display = gr.Textbox(label="目前角色", interactive=False)
                log_file_path_display = gr.Textbox(label="日誌檔案路徑 (偵測)", interactive=False)
                # 優先使用伺服器回傳的精確路徑（每會話專屬）
                log_path_state = gr.State(None)
                log_table = gr.Dataframe(
                    headers=["timestamp", "user_input", "response_options", "selected_response"],
                    datatype=["str", "str", "str", "str"],
                    row_count=(0, "dynamic"),
                    col_count=(4, "fixed"),
                    wrap=True,
                    label="對話紀錄 (近期)"
                )
                refresh_logs_btn = gr.Button("刷新紀錄")

                @log_function_call
                def _mask_text(text: str) -> str:
                    try:
                        if not text:
                            return text
                        s = str(text)
                        # 簡單遮蔽身分證樣式與電話（示意，非嚴格）
                        import re
                        s = re.sub(r"([A-Z][0-9]{9})", r"\1*****", s)
                        s = re.sub(r"(\d{3,4})[- ]?(\d{3,4})[- ]?(\d{3,4})", r"***-***-****", s)
                        return s
                    except Exception:
                        return str(text)

                @log_function_call
                def fetch_local_logs(char_name: str, sess_id: str | None, limit: int, mask: bool, path_override: str | None):
                    """讀取本地 logs/api 的 JSON 行對話紀錄，回傳表格資料與檔案路徑。"""
                    try:
                        # 1) 優先使用伺服器提供的每會話檔案路徑
                        target_file = path_override if (path_override and os.path.exists(path_override)) else None

                        # 2) 其次，若有 session_id，嘗試以 session 短ID 精確定位 per-session 檔案
                        if not target_file and sess_id and isinstance(sess_id, str) and len(sess_id) >= 8:
                            sess_short = sess_id[:8]
                            api_dir = os.path.join(project_root, "logs", "api")
                            if os.path.isdir(api_dir):
                                # 收集符合模式 *_{char}_sess_{short}_chat_gui.log 的所有檔案，取最新
                                latest_path, latest_mtime = None, -1
                                for fname in os.listdir(api_dir):
                                    if fname.endswith("_chat_gui.log") and f"_{char_name}_sess_{sess_short}_" in fname:
                                        fpath = os.path.join(api_dir, fname)
                                        try:
                                            mtime = os.path.getmtime(fpath)
                                            if mtime > latest_mtime:
                                                latest_mtime = mtime
                                                latest_path = fpath
                                        except Exception:
                                            continue
                                target_file = latest_path

                        # 3) 最後，再以角色名稱掃描所有可能檔案（legacy 與 per-session），擇其新者
                        if not target_file:
                            api_dir = os.path.join(project_root, "logs", "api")
                            latest_path, latest_mtime = None, -1
                            if os.path.isdir(api_dir):
                                for fname in os.listdir(api_dir):
                                    # legacy: *_patient_{char}_chat_gui.log
                                    legacy_match = fname.endswith(f"_patient_{char_name}_chat_gui.log")
                                    # per-session: *_{char}_sess_*_chat_gui.log
                                    session_match = (fname.endswith("_chat_gui.log") and f"_{char_name}_sess_" in fname)
                                    if legacy_match or session_match:
                                        fpath = os.path.join(api_dir, fname)
                                        try:
                                            mtime = os.path.getmtime(fpath)
                                            if mtime > latest_mtime:
                                                latest_mtime = mtime
                                                latest_path = fpath
                                        except Exception:
                                            continue
                            target_file = latest_path

                        rows: list[list[str]] = []
                        if target_file and os.path.exists(target_file):
                            # 讀取最後 limit 行
                            lines: list[str] = []
                            with open(target_file, "r", encoding="utf-8") as f:
                                for line in f:
                                    if line.strip():
                                        lines.append(line.rstrip("\n"))
                            tail = lines[-int(limit):] if limit and limit > 0 else lines

                            import json as _json
                            for ln in tail:
                                try:
                                    rec = _json.loads(ln)
                                except Exception:
                                    continue
                                ts = str(rec.get("timestamp", ""))
                                q = str(rec.get("user_input", ""))
                                opts = rec.get("response_options", [])
                                sel = rec.get("selected_response", None)
                                if not isinstance(opts, list):
                                    opts = [str(opts)] if opts else []
                                opts_str = "\n".join(f"{i+1}. {str(o)}" for i, o in enumerate(opts))
                                sel_str = str(sel) if sel is not None else ""
                                if mask:
                                    ts = _mask_text(ts)
                                    q = _mask_text(q)
                                    opts_str = _mask_text(opts_str)
                                    sel_str = _mask_text(sel_str)
                                rows.append([ts, q, opts_str, sel_str])
                        else:
                            target_file = target_file or "(未找到)"
                        # 更新三個顯示欄位
                        return (
                            sess_id or "(無)",
                            char_name or "(未選擇)",
                            str(target_file),
                            rows
                        )
                    except Exception as e:
                        logger.error(f"讀取本地紀錄失敗: {e}")
                        return (sess_id or "(無)", char_name or "(未選擇)", "(錯誤)", [])

                # 綁定刷新邏輯
                refresh_logs_btn.click(
                    fn=fetch_local_logs,
                    inputs=[text_selector, session_id_text, log_limit, log_mask, log_path_state],
                    outputs=[current_session_display, current_character_display, log_file_path_display, log_table]
                )

                # 角色變更時自動更新一次
                text_selector.change(
                    fn=fetch_local_logs,
                    inputs=[text_selector, session_id_text, log_limit, log_mask, log_path_state],
                    outputs=[current_session_display, current_character_display, log_file_path_display, log_table]
                )

            # 移除自動清除會話的 page-load 綁定；瀏覽器重新整理會重建 UI 與 ApiClient，自然建立新會話
            
            # Add back the text dialogue button handlers before the return statement
            # 設置文本對話按鈕點擊事件
            response_btn1.click(
                fn=handle_response_btn_click,
                inputs=[response_btn1, text_chatbot, session_id_text],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            ).then(
                fn=_clear_text_input,
                inputs=[],
                outputs=[text_input]
            )

            response_btn2.click(
                fn=handle_response_btn_click,
                inputs=[response_btn2, text_chatbot, session_id_text],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            ).then(
                fn=_clear_text_input,
                inputs=[],
                outputs=[text_input]
            )

            response_btn3.click(
                fn=handle_response_btn_click,
                inputs=[response_btn3, text_chatbot, session_id_text],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            ).then(
                fn=_clear_text_input,
                inputs=[],
                outputs=[text_input]
            )

            response_btn4.click(
                fn=handle_response_btn_click,
                inputs=[response_btn4, text_chatbot, session_id_text],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            ).then(
                fn=_clear_text_input,
                inputs=[],
                outputs=[text_input]
            )

            response_btn5.click(
                fn=handle_response_btn_click,
                inputs=[response_btn5, text_chatbot, session_id_text],
                outputs=[text_chatbot, session_id_text, response_options]
            ).then(
                fn=update_response_buttons,
                inputs=[response_options],
                outputs=[response_box, response_btn1, response_btn2, response_btn3, response_btn4, response_btn5]
            ).then(
                fn=_clear_text_input,
                inputs=[],
                outputs=[text_input]
            )
        
            # ------------------------
            # Page-load: reset session safely (refresh => new session)
            # ------------------------
            @log_function_call
            def _on_page_load_reset_session():
                try:
                    self.api_client.reset_session()
                except Exception:
                    pass
                # 清空每會話日誌覆寫路徑
                try:
                    log_path_state.value = None
                except Exception:
                    pass
                # 清空兩個會話狀態；不回傳其他尚未保證存在的狀態，避免綁定不匹配
                return None, None

            # 綁定 page-load 事件：瀏覽器重新整理即清空會話（不影響其他元件）
            app.load(
                fn=_on_page_load_reset_session,
                inputs=[],
                outputs=[session_id_text, session_id_audio]
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
