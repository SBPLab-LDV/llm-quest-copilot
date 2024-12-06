import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
from ..core.dialogue import DialogueManager
from ..utils.config import load_character, list_available_characters

class ChatWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("口腔癌病患對話系統")
        self.root.geometry("800x600")
        
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
        
        self.input_field = ttk.Entry(self.input_frame, width=60)
        self.input_field.grid(row=0, column=0, padx=5)
        
        self.send_button = ttk.Button(
            self.input_frame, text="發送", command=self.send_message)
        self.send_button.grid(row=0, column=1, padx=5)
        
        # 綁定 Enter 鍵
        self.input_field.bind("<Return>", lambda e: self.send_message())

    def select_character(self, char_id):
        """選擇病患"""
        self.character = load_character(char_id)
        self.dialogue_manager = DialogueManager(self.character)
        
        # 切換到對話介面
        self.selection_frame.grid_remove()
        self.chat_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 顯示歡迎訊息
        welcome_msg = (f"=== 開始與 {self.character.name} 對話 ===\n"
                      f"病患背景: {self.character.persona}\n"
                      f"目標: {self.character.goal}\n\n")
        self.chat_history.insert(tk.END, welcome_msg)

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
            self.root.after(0, self.display_response, response)
        
        asyncio.run(handle_response())

    def display_response(self, response):
        """顯示回應"""
        self.chat_history.insert(tk.END, f"\n{self.character.name}: {response}\n")
        self.chat_history.see(tk.END) 