from typing import Optional, List, Union
import google.generativeai as genai
import json
import re
from .character import Character
from .state import DialogueState
from ..llm.gemini_client import GeminiClient
from .prompt_manager import PromptManager
import keyboard
import datetime  # 導入 datetime 模組
import os # 導入 os 模組，用於檔案路徑操作
import logging

class DialogueManager:
    def __init__(self, character: Character, use_terminal: bool = False, log_dir: str = "logs"):
        """Initialize the DialogueManager.
        
        Args:
            character: Character instance containing the NPC's information (as patient identifier)
            use_terminal: Whether to use terminal mode for interaction
            log_dir: Directory to save interaction logs
        """
        # 打印診斷信息
        logger = logging.getLogger(__name__)
        logger.debug(f"DialogueManager.__init__ 被調用，參數: character={character}, use_terminal={use_terminal}, log_dir={log_dir}")
        logger.debug(f"參數類型: character={type(character)}, use_terminal={type(use_terminal)}, log_dir={type(log_dir)}")
        
        self.character = character
        self.current_state = DialogueState.NORMAL
        self.conversation_history = []
        self.gemini_client = GeminiClient()
        self.prompt_manager = PromptManager()
        self.use_terminal = use_terminal
        self.interaction_log = []
        self.log_dir = log_dir # 設定log directory

        # 確保日誌目錄存在
        os.makedirs(self.log_dir, exist_ok=True)

        # 根據角色名稱和日期決定日誌檔案名稱
        today_date_str = datetime.datetime.now().strftime("%Y%m%d")
        self.log_filename = f"{today_date_str}_patient_{self.character.name}_chat_{'terminal' if self.use_terminal else 'gui'}.log"
        self.log_filepath = os.path.join(self.log_dir, self.log_filename)

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

    def log_interaction(self, user_input: str, response_options: list, selected_response: Optional[str] = None):
        """記錄使用者輸入、回應選項和選擇的回應。

        Args:
            user_input: 使用者的輸入文字。
            response_options: LLM 生成的回應選項列表。
            selected_response: 使用者選擇的回應，如果沒有選擇則為 None。
        """
        timestamp = datetime.datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "user_input": user_input,
            "response_options": response_options,
            "selected_response": selected_response
        }
        self.interaction_log.append(log_entry)
        print(f"互動已記錄：{log_entry}") # 可以選擇性地印出或儲存到檔案

    def save_interaction_log(self):
        """將互動日誌儲存到 JSON 檔案 (追加模式)."""
        if not self.interaction_log:
            print("沒有互動日誌可以儲存。")
            return

        try:
            with open(self.log_filepath, 'a', encoding='utf-8') as f: # 使用 'a' 模式 (append)
                for entry in self.interaction_log: # 逐條寫入 log entry
                    json.dump(entry, f, ensure_ascii=False)
                    f.write('\n') # 每條記錄後換行，方便閱讀和後續處理
            print(f"互動日誌已追加儲存到: {self.log_filepath}")
            self.interaction_log = [] # 儲存後清空當前log，準備記錄下一輪對話
        except Exception as e:
            print(f"儲存互動日誌時發生錯誤: {e}")


    async def process_turn(self, user_input: str, gui_selected_response: Optional[str] = None) -> Union[str, dict]:
        """Process one turn of dialogue.
        
        Args:
            user_input: The user's input text
            gui_selected_response: 病患在 GUI 上選擇的回應 (optional, for GUI mode)
            
        Returns:
            Either a string response (terminal mode) or JSON response (GUI mode)
        """
        try:
            # 記錄用戶輸入
            self.conversation_history.append(f"護理人員: {user_input}")
            
            # 使用 PromptManager 生成提示詞
            prompt = self.prompt_manager.generate_prompt(
                user_input=user_input,
                character=self.character,
                current_state=self.current_state.value,
                conversation_history=self._format_conversation_history()
            )
            
            # 記錄提示詞 - 新增記錄
            logger = logging.getLogger(__name__)
            logger.debug(f"===== 發送至 LLM 的提示詞 =====")
            logger.debug(f"{prompt}")
            logger.debug(f"===== 提示詞結束 =====")

            # 獲取回應
            response = self.gemini_client.generate_response(prompt)
            
            # 記錄 LLM 的原始回應 - 新增記錄
            logger.debug(f"===== 收到的 LLM 原始回應 =====")
            logger.debug(f"{response}")
            logger.debug(f"===== 原始回應結束 =====")
            
            print(response)
            
            # 清理並解析JSON
            cleaned_response = self._clean_json_string(response)
            
            # 記錄清理後的回應 - 新增記錄
            logger.debug(f"===== 清理後的 JSON 回應 =====")
            logger.debug(f"{cleaned_response}")
            logger.debug(f"===== 清理後回應結束 =====")
            
            response_dict = json.loads(cleaned_response)
            
            # 驗證回應格式
            if not isinstance(response_dict, dict):
                raise ValueError("回應格式錯誤：不是有效的JSON物件")
            
            if "responses" not in response_dict or "state" not in response_dict or "dialogue_context" not in response_dict:
                raise ValueError("回應格式錯誤：缺少必要的欄位")
            
            if not isinstance(response_dict["responses"], list):
                raise ValueError("回應格式錯誤：responses 不是陣列")
            
            # 更新狀態
            new_state = response_dict["state"]
            try:
                self.current_state = DialogueState(new_state)
            except ValueError:
                self.current_state = DialogueState.CONFUSED

            # 取得對話情境
            dialogue_context = response_dict["dialogue_context"]
            print(f"LLM 判斷的對話情境: {dialogue_context}")

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

                response_options_for_log = response_dict["responses"] # 記錄選項

                while True:
                    event = keyboard.read_event(suppress=True)
                    if event.event_type == 'down':
                        if event.name == '0':
                            print("\n跳過此輪回應，請繼續對話")
                            self.conversation_history.append("(跳過此輪回應)")
                            self.log_interaction(user_input, response_options_for_log, selected_response="(跳過此輪回應)") # 記錄跳過
                            self.save_interaction_log() # 儲存日誌
                            return ""
                        elif event.name == 'q':
                            print("\n結束對話")
                            self.save_interaction_log() # 儲存對話記錄 (最後一輪)
                            return "quit"
                        elif event.name in ['1', '2', '3', '4', '5']:
                            choice = int(event.name)
                            if choice <= len(response_dict["responses"]):
                                selected_response = response_dict["responses"][choice - 1]
                                print(f"\n已選擇選項 {choice}: {selected_response}")
                                self.conversation_history.append(f"{self.character.name}: {selected_response}")
                                self.log_interaction(user_input, response_options_for_log, selected_response=selected_response) # 記錄選擇的回應
                                self.save_interaction_log() # 儲存日誌
                                return selected_response
            else:
                # 返回 JSON 格式的回應供 GUI 使用
                cleaned_response_for_log = cleaned_response # 記錄整個 JSON 回應
                self.log_interaction(user_input, response_dict["responses"], selected_response=gui_selected_response) # GUI 模式下記錄病患選擇
                self.save_interaction_log() # 儲存日誌
                return cleaned_response
            
        except json.JSONDecodeError as e:
            self.current_state = DialogueState.CONFUSED
            error_text = f"JSONDecodeError: {e}"
            error_payload = {
                "responses": [error_text],
                "state": "ERROR",
                "dialogue_context": "JSON_DECODE_ERROR",
                "error": {
                    "type": "JSONDecodeError",
                    "message": str(e)
                }
            }
            error_response_json_string = json.dumps(error_payload, ensure_ascii=False)
            self.log_interaction(user_input, error_response_json_string, selected_response=None)
            self.save_interaction_log()
            return error_response_json_string if not self.use_terminal else error_text

        except Exception as e:
            self.current_state = DialogueState.CONFUSED
            error_text = f"Exception[{type(e).__name__}]: {e}"
            error_payload = {
                "responses": [error_text],
                "state": "ERROR",
                "dialogue_context": "UNHANDLED_EXCEPTION",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
            error_response_json_string = json.dumps(error_payload, ensure_ascii=False)
            self.log_interaction(user_input, error_response_json_string, selected_response=None)
            self.save_interaction_log()
            return error_response_json_string if not self.use_terminal else error_text
