import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
import threading
import json
from ..core.dialogue import DialogueManager
from ..utils.config import load_character, list_available_characters, load_config
from ..utils.speech_input import SpeechInput

class ChatWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("口腔癌病患對話系統")
        self.root.geometry("800x600")
        
        # 載入設定
        self.config = load_config()
        
        # 初始化語音輸入
        if self.config.get('input_mode') == 'voice':
            self.speech_input = SpeechInput(
                self.config['google_api_key'],
                save_recordings=self.config.get('save_recordings', False),
                debug_mode=self.config.get('debug_mode', False)
            )
        else:
            self.speech_input = None
        
        # 建立主要框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 病患選擇區域
        self.setup_character_selection()
        
        # 對話區域（初始隱藏）
        self.chat_frame = ttk.Frame(self.main_frame)
        self.setup_chat_area()
        
        # 初始化對話管理器
        self.dialogue_manager = None
        self.character = None
        
        # 錄音狀態
        self.is_recording = False
        self.recording_thread = None
        
        # 回應選項按鈕
        self.response_buttons = []

    def setup_character_selection(self):
        """設置病患選擇介面"""
        self.selection_frame = ttk.Frame(self.main_frame)
        self.selection_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 標題
        ttk.Label(self.selection_frame, 
                 text="請選擇要對話的病患：", 
                 font=('Arial', 12, 'bold')).grid(row=0, column=0, pady=10)
        
        # 病患列表
        self.character_list = ttk.Frame(self.selection_frame)
        self.character_list.grid(row=1, column=0, pady=10)
        
        # 載入病患資料
        characters = list_available_characters()
        for i, (char_id, char_data) in enumerate(characters.items()):
            char_frame = ttk.Frame(self.character_list)
            char_frame.grid(row=i, column=0, pady=5, sticky=tk.W)
            
            ttk.Label(char_frame, 
                     text=f"[{char_id}] {char_data['name']}", 
                     font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky=tk.W)
            ttk.Label(char_frame, 
                     text=f"背景: {char_data['persona']}", 
                     wraplength=600).grid(row=1, column=0, sticky=tk.W)
            ttk.Label(char_frame, 
                     text=f"狀況: {char_data['backstory']}", 
                     wraplength=600).grid(row=2, column=0, sticky=tk.W)
            
            # 選擇按鈕
            ttk.Button(char_frame, 
                      text="選擇此病患", 
                      command=lambda id=char_id: self.select_character(id)).grid(row=3, column=0, pady=5)

    def setup_chat_area(self):
        """設置對話介面"""
        # 對話歷史顯示區
        self.chat_history = scrolledtext.ScrolledText(
            self.chat_frame, wrap=tk.WORD, width=70, height=20)
        self.chat_history.grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        
        # 輸入區域
        self.input_frame = ttk.Frame(self.chat_frame)
        self.input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.input_field = ttk.Entry(self.input_frame, width=50)
        self.input_field.grid(row=0, column=0, padx=5)
        
        # 發���按鈕
        self.send_button = ttk.Button(
            self.input_frame, text="發送", command=self.send_message)
        self.send_button.grid(row=0, column=1, padx=5)
        
        # 語音輸入按鈕
        if self.speech_input:
            self.voice_button = ttk.Button(
                self.input_frame, 
                text="按住說話", 
                command=lambda: None)
            self.voice_button.grid(row=0, column=2, padx=5)
            
            # 綁定按鈕事件
            self.voice_button.bind('<ButtonPress-1>', self.start_recording)
            self.voice_button.bind('<ButtonRelease-1>', self.stop_recording)
            
            # 錄音狀態標籤
            self.recording_label = ttk.Label(
                self.input_frame, 
                text="", 
                foreground="red")
            self.recording_label.grid(row=0, column=3, padx=5)
        
        # 回應選項區域
        self.response_frame = ttk.Frame(self.chat_frame)
        self.response_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # 綁定 Enter 鍵
        self.input_field.bind("<Return>", lambda e: self.send_message())

    def select_character(self, char_id):
        """選擇病患"""
        self.character = load_character(char_id)
        self.dialogue_manager = DialogueManager(self.character, use_terminal=False)
        
        # 切換到對話介面
        self.selection_frame.grid_remove()
        self.chat_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 顯示歡迎訊息
        welcome_msg = (f"=== 開始與 {self.character.name} 對話 ===\n"
                      f"病患背景: {self.character.persona}\n"
                      f"目標: {self.character.goal}\n\n")
        self.chat_history.insert(tk.END, welcome_msg)

    def display_response_options(self, response_json):
        """顯示回應選項按鈕"""
        # 清除現有按鈕
        for button in self.response_buttons:
            button.destroy()
        self.response_buttons.clear()
        
        try:
            # 解析回應 JSON
            response_data = json.loads(response_json)
            responses = response_data.get("responses", [])
            
            # 創建新按鈕
            for i, response in enumerate(responses):
                button = ttk.Button(
                    self.response_frame,
                    text=f"{i+1}. {response}",
                    command=lambda r=response: self.select_response(r)
                )
                button.grid(row=i//2, column=i%2, padx=5, pady=2, sticky=(tk.W, tk.E))
                self.response_buttons.append(button)
            
            # 添加"跳過"選項按鈕
            skip_button = ttk.Button(
                self.response_frame,
                text="0. 這些選項都不適合（跳過，請繼續提問）",
                command=lambda: self.select_response(None)
            )
            skip_button.grid(row=(len(responses)+1)//2, column=0, columnspan=2, 
                           padx=5, pady=2, sticky=(tk.W, tk.E))
            self.response_buttons.append(skip_button)
                
        except json.JSONDecodeError:
            # 如果不是 JSON 格式，直接顯示文本
            self.chat_history.insert(tk.END, f"\n{self.character.name}: {response_json}\n")
            self.chat_history.see(tk.END)

    def select_response(self, response):
        """選擇回應選項"""
        # 顯示選擇的回應或跳過提示
        if response is None:
            self.chat_history.insert(tk.END, "\n(跳過此輪回應)\n")
            self.chat_history.insert(tk.END, "\n請繼續提問...\n")
        else:
            self.chat_history.insert(tk.END, f"\n{self.character.name}: {response}\n")
            self.chat_history.insert(tk.END, "\n請繼續提問...\n")
        
        self.chat_history.see(tk.END)
        
        # 清除選項按鈕
        for button in self.response_buttons:
            button.destroy()
        self.response_buttons.clear()

    async def process_message(self, message):
        """處理訊息"""
        response = await self.dialogue_manager.process_turn(message)
        return response

    def send_message(self):
        """發送訊息"""
        message = self.input_field.get().strip()
        if not message:
            return
        
        # 清空輸入框
        self.input_field.delete(0, tk.END)
        
        # 顯示護理人員訊息
        self.chat_history.insert(tk.END, f"\n護理人員: {message}\n")
        self.chat_history.see(tk.END)
        
        # 非同步處理回應
        async def handle_response():
            response = await self.process_message(message)
            self.root.after(0, self.display_response_options, response)
        
        asyncio.run(handle_response())

    def start_recording(self, event):
        """開始錄音"""
        if not self.is_recording and self.speech_input:
            self.is_recording = True
            self.recording_label.config(text="正在錄音...")
            self.voice_button.config(text="放開結束")
            
            # 在新線程中開始錄音
            self.recording_thread = threading.Thread(
                target=self.speech_input.start_recording
            )
            self.recording_thread.start()

    def stop_recording(self, event):
        """停止錄音並處理語音"""
        if self.is_recording and self.speech_input:
            self.is_recording = False
            self.recording_label.config(text="處理中...")
            self.voice_button.config(text="按住說話")
            
            # 停止錄音並獲取文字
            def process_recording():
                text = self.speech_input.stop_recording()
                if text:
                    # 使用 after 方法在主線程中更新 UI
                    self.root.after(0, self.handle_voice_result, text)
                else:
                    self.root.after(0, self.recording_label.config, {"text": ""})
            
            # 在新線程中處理錄音結果
            threading.Thread(target=process_recording).start()
    
    def handle_voice_result(self, text):
        """處理語音識別結果"""
        self.input_field.delete(0, tk.END)
        self.input_field.insert(0, text)
        self.send_message()
        self.recording_label.config(text="")