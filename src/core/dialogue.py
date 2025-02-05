from typing import Optional, List, Union
import google.generativeai as genai
import json
import re
from .character import Character
from .state import DialogueState
from ..llm.gemini_client import GeminiClient
from .prompt_manager import PromptManager
import keyboard

class DialogueManager:
    def __init__(self, character: Character, use_terminal: bool = False):
        """Initialize the DialogueManager.
        
        Args:
            character: Character instance containing the NPC's information
            use_terminal: Whether to use terminal mode for interaction
        """
        self.character = character
        self.current_state = DialogueState.NORMAL
        self.conversation_history = []
        self.gemini_client = GeminiClient()
        self.prompt_manager = PromptManager()
        self.use_terminal = use_terminal

    def _format_conversation_history(self) -> List[str]:
        """Format the conversation history.
        
        Returns:
            List of the last 5 conversation turns
        """
        return self.conversation_history[-5:]  # 只保留最近5輪對話
    
    def _clean_json_string(self, text: str) -> str:
        """Clean and format JSON string.
        
        Args:
            text: Raw JSON string to clean
            
        Returns:
            Cleaned JSON string
        """
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

    async def process_turn(self, user_input: str) -> Union[str, dict]:
        """Process one turn of dialogue.
        
        Args:
            user_input: The user's input text
            
        Returns:
            Either a string response (terminal mode) or JSON response (GUI mode)
        """
        try:
            # 記錄用戶輸入
            self.conversation_history.append(f"護理人員: {user_input}")
            
            # 使用 PromptManager 生成提示詞
            prompt = self.prompt_manager.generate_prompt(
                user_input=user_input,
                character_name=self.character.name,
                persona=self.character.persona,
                backstory=self.character.backstory,
                goal=self.character.goal,
                current_state=self.current_state.value,
                conversation_history=self._format_conversation_history()
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
            
            # 更新狀態
            new_state = response_dict["state"]
            try:
                self.current_state = DialogueState(new_state)
            except ValueError:
                self.current_state = DialogueState.CONFUSED

            # 評估回應品質
            evaluation_prompt = self.prompt_manager.get_evaluation_prompt(
                current_state=self.current_state.value,
                player_input=user_input,
                response=cleaned_response
            )
            # TODO: 使用評估結果來改進回應品質

            if self.use_terminal:
                # 在終端機中處理選項
                print(f"\n{self.character.name} 的回應選項：")
                for i, response in enumerate(response_dict["responses"], 1):
                    print(f"{i}. {response}")
                print("0. 這些選項都不適合（跳過，直接進入下一輪對話）")
                print("q. 結束對話")
                print("\n請按數字鍵 0-5 選擇選項，或按 q 結束對話...")
                
                while True:
                    event = keyboard.read_event(suppress=True)
                    if event.event_type == 'down':
                        if event.name == '0':
                            print("\n跳過此輪回應，請繼續對話")
                            self.conversation_history.append("(跳過此輪回應)")
                            return ""
                        elif event.name == 'q':
                            print("\n結束對話")
                            return "quit"
                        elif event.name in ['1', '2', '3', '4', '5']:
                            choice = int(event.name)
                            if choice <= len(response_dict["responses"]):
                                selected_response = response_dict["responses"][choice - 1]
                                print(f"\n已選擇選項 {choice}: {selected_response}")
                                self.conversation_history.append(f"{self.character.name}: {selected_response}")
                                return selected_response
            else:
                # 返回 JSON 格式的回應供 GUI 使用
                return cleaned_response
            
        except json.JSONDecodeError as e:
            self.current_state = DialogueState.CONFUSED
            error_response = {
                "responses": ["對不起，我現在有點混亂，能請你重複一次嗎？"],
                "state": self.current_state.value
            }
            return json.dumps(error_response) if not self.use_terminal else "對不起，我現在有點混亂，能請你重複一次嗎？"
            
        except Exception as e:
            self.current_state = DialogueState.CONFUSED
            error_response = {
                "responses": ["抱歉，我現在無法正確回應"],
                "state": self.current_state.value
            }
            return json.dumps(error_response) if not self.use_terminal else "抱歉，我現在無法正確回應"
