import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
from ..core.dialogue import DialogueManager
from ..utils.config import load_character, list_available_characters
import json

class ChatWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("口腔癌病患對話系統")
        self.root.geometry("800x800")
        
        # 建立主要框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 病患選擇區域
        self.setup_character_selection()
        
        # 對話區域（初始隱藏）
        self.chat_frame = ttk.Frame(self.main_frame)
        self.setup_chat_area()
        
        # 初始化對話管理器和對話歷史
        self.dialogue_manager = None
        self.character = None
        self.conversation_history = []
        
        # 選項按鈕列表
        self.option_buttons = []
        
        # 配置根窗口的網格權重
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        
        # 配置主框架的網格權重
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

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
        self.chat_history.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 選項區域（在對話歷史下方）
        self.options_frame = ttk.Frame(self.chat_frame)
        self.options_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        # 輸入區域（在選項區域下方）
        self.input_frame = ttk.Frame(self.chat_frame)
        self.input_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        self.input_field = ttk.Entry(self.input_frame, width=50)
        self.input_field.grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        
        self.send_button = ttk.Button(
            self.input_frame, text="發送", command=self.send_message)
        self.send_button.grid(row=0, column=1, padx=5)
        
        # 綁定 Enter 鍵
        self.input_field.bind("<Return>", lambda e: self.send_message())
        
        # 配置網格權重
        self.chat_frame.grid_rowconfigure(0, weight=3)  # 對話歷史佔較多空間
        self.chat_frame.grid_rowconfigure(1, weight=1)  # 選項區域佔較少空間
        self.chat_frame.grid_columnconfigure(0, weight=1)

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

    async def process_message(self, message):
        """處理訊息"""
        response = await self.dialogue_manager.process_turn(message)
        return response

    def handle_response_display(self, response):
        """處理回應顯示和選項"""
        try:
            # 清除現有選項
            self.clear_options()
            
            # 嘗試解析 JSON 回應
            response_dict = json.loads(response)
            
            # 顯示回應文字
            if isinstance(response_dict.get("responses", []), list):
                responses = response_dict["responses"]
                if responses:
                    # 只顯示選項按鈕，不在對話框中顯示選項列表
                    self.display_options(responses)
            else:
                response_text = response_dict.get("responses", "無回應")
                self.chat_history.insert(tk.END, f"\n{self.character.name}: {response_text}\n")
                
            # 顯示狀態
            if "state" in response_dict:
                self.chat_history.insert(tk.END, f"[當前狀態: {response_dict['state']}]\n")
                
        except json.JSONDecodeError:
            # 如果不是 JSON 格式，直接顯示文字
            self.chat_history.insert(tk.END, f"\n{self.character.name}: {response}\n")
        
        self.chat_history.see(tk.END)

    def display_options(self, options):
        """顯示選項按鈕"""
        # 清除現有選項
        self.clear_options()
        
        # 計算每行顯示的按鈕數
        buttons_per_row = 2
        
        # 創建並顯示選項按鈕
        for i, option in enumerate(options):
            btn = ttk.Button(
                self.options_frame,
                text=f"{i+1}. {option}",
                command=lambda opt=option, num=i+1: self.select_option(opt, num),
                width=40  # 設定按鈕寬度
            )
            row = i // buttons_per_row
            col = i % buttons_per_row
            btn.grid(row=row, column=col, padx=5, pady=2, sticky='ew')
            self.option_buttons.append(btn)
        
        # 添加跳過選項按鈕
        skip_btn = ttk.Button(
            self.options_frame,
            text="0. 跳過選項",
            command=lambda: self.select_option(None, 0),
            width=20
        )
        skip_btn.grid(
            row=(len(options) + buttons_per_row - 1) // buttons_per_row,
            column=0,
            columnspan=2,
            pady=5,
            sticky='ew'
        )
        self.option_buttons.append(skip_btn)
        
        # 配置列的權重
        for i in range(buttons_per_row):
            self.options_frame.grid_columnconfigure(i, weight=1)

    def select_option(self, option, number):
        """選擇一個選項"""
        if option is not None:
            # 顯示選擇的選項作為病患的回答
            self.chat_history.insert(tk.END, f"\n{self.character.name}: {option}\n")
            self.chat_history.see(tk.END)
            
            # 記錄到對話歷史
            self.conversation_history.append(f"{self.character.name}: {option}")
            
            # 禁用所有選項按鈕
            for btn in self.option_buttons:
                btn.configure(state='disabled')
                
            # 添加提示，讓護理人員知道換他輸入了
            self.chat_history.insert(tk.END, "\n=== 請護理人員繼續提問 ===\n")
            self.chat_history.see(tk.END)
            
            # 聚焦到輸入框
            self.input_field.focus_set()
        else:
            # 跳過選項
            self.chat_history.insert(tk.END, "\n[跳過此輪回應]\n")
            self.chat_history.insert(tk.END, "\n=== 請護理人員繼續提問 ===\n")
            self.chat_history.see(tk.END)
            # 禁用所有選項按鈕
            for btn in self.option_buttons:
                btn.configure(state='disabled')
            # 聚焦到輸入框
            self.input_field.focus_set()

    def send_message(self):
        """發送訊息"""
        message = self.input_field.get().strip()
        if not message:
            return
        
        # 清空輸入框
        self.input_field.delete(0, tk.END)
        
        # 禁用輸入區域
        self.disable_input()
        
        # 顯示護理人員訊息
        self.chat_history.insert(tk.END, f"\n護理人員: {message}\n")
        self.chat_history.see(tk.END)
        
        # 非同步處理回應
        async def handle_response():
            try:
                response = await self.process_message(message)
                self.root.after(0, self.handle_response_display, response)
            except Exception as e:
                self.root.after(0, self.display_error, str(e))
            finally:
                self.root.after(0, self.enable_input)
        
        # 使用 asyncio 執行非同步任務
        asyncio.run(handle_response())

    def display_error(self, error):
        """顯示錯誤訊息"""
        self.chat_history.insert(tk.END, f"\n發生錯誤: {error}\n")
        self.chat_history.see(tk.END)

    def clear_options(self):
        """清除選項按鈕"""
        for btn in self.option_buttons:
            btn.destroy()
        self.option_buttons = []

    def disable_input(self):
        """禁用輸入區域"""
        self.input_field.config(state=tk.DISABLED)
        self.send_button.config(state=tk.DISABLED)

    def enable_input(self):
        """啟用輸入區域"""
        self.input_field.config(state=tk.NORMAL)
        self.send_button.config(state=tk.NORMAL) 