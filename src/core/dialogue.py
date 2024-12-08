from typing import Optional, List
import google.generativeai as genai
import json
import re
from .character import Character
from .state import DialogueState
from ..llm.gemini_client import GeminiClient
from ..utils.config import load_prompts
import keyboard

class DialogueManager:
    def __init__(self, character: Character):
        self.character = character
        self.current_state = DialogueState.NORMAL
        self.conversation_history = []
        self.gemini_client = GeminiClient()
        self.prompts = load_prompts()

    def _format_conversation_history(self) -> str:
        """格式化對話歷史"""
        return "\n".join(self.conversation_history[-5:])  # 只保留最近5輪對話
    
    def _clean_json_string(self, text: str) -> str:
        """清理並格式化JSON字串"""
        # 移除可能的前導和尾隨非JSON內容
        text = text.strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]
        
        # 修復常見的JSON格式問題
        text = text.replace('\\n', '\n')  # 處理換行符
        text = text.replace('..."', '"')  # 移除省略號
        text = text.replace('...',  '')   # 移除省略號
        
        return text

    async def process_turn(self, user_input: str) -> str:
        """處理一輪對話"""
        try:
            # 記錄用戶輸入
            self.conversation_history.append(f"護理人員: {user_input}")
            
            # 準備提示詞
            prompt = self.prompts['character_response'].format(
                name=self.character.name,
                persona=self.character.persona,
                backstory=self.character.backstory,
                goal=self.character.goal,
                current_state=self.current_state.value,
                conversation_history=self._format_conversation_history(),
                user_input=user_input
            )

            # 獲取回應
            response = self.gemini_client.generate_response(prompt)
            
            # 清理並解析JSON
            cleaned_response = self._clean_json_string(response)
            response_dict = json.loads(cleaned_response)
            
            # 驗證回應格式
            if not isinstance(response_dict, dict):
                raise ValueError("回應格式錯誤：不是有效的JSON物件")
            
            if "responses" not in response_dict or "state" not in response_dict:
                raise ValueError("回應格式錯誤：缺少必要的欄位")
            
            if not isinstance(response_dict["responses"], list):
                raise ValueError("回應格式錯誤：responses 不是陣列")
            
            # 取得回應（現在只會有一個）
            selected_response = response_dict["responses"][0]
            
            # 更新狀態
            new_state = response_dict["state"]
            try:
                self.current_state = DialogueState(new_state)
            except ValueError:
                self.current_state = DialogueState.CONFUSED

            # 顯示所有選項供使用者選擇
            print("\n請選擇一個回應選項：")
            for i, response in enumerate(response_dict["responses"], 1):
                print(f"{i}. {response}")
            print("\n請按數字鍵 1-5 選擇選項...")
            
            while True:
                event = keyboard.read_event(suppress=True)
                if event.event_type == 'down':
                    if event.name in ['1', '2', '3', '4', '5']:
                        choice = int(event.name)
                        selected_response = response_dict["responses"][choice - 1]
                        print(f"\n已選擇選項 {choice}")
                        break
            
            # 記錄 NPC 回應
            self.conversation_history.append(f"{self.character.name}: {selected_response}")
            
            return f"{selected_response}\n當前對話狀態: {self.current_state.value}"
            
        except json.JSONDecodeError as e:
            print(f"JSON解析錯誤: {e}")  # 用於調試
            self.current_state = DialogueState.CONFUSED
            error_response = "對不起，我現在有點混亂，能請你重複一次嗎？"
            self.conversation_history.append(f"{self.character.name}: {error_response}")
            return f"{error_response}\n當前對話狀態: {self.current_state.value}"
            
        except Exception as e:
            print(f"其他錯誤: {e}")  # 用於調試
            self.current_state = DialogueState.CONFUSED
            error_response = "抱歉，我現在無法正確回應"
            self.conversation_history.append(f"{self.character.name}: {error_response}")
            return f"{error_response}\n當前對話狀態: {self.current_state.value}"