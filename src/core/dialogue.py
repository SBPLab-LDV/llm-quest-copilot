from typing import Optional, List
import google.generativeai as genai
from .character import Character
from .state import DialogueState
from ..llm.gemini_client import GeminiClient
from ..utils.config import load_prompts

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

    async def process_turn(self, user_input: str) -> str:
        """處理一輪對話"""
        # 記錄用戶輸入
        self.conversation_history.append(f"玩家: {user_input}")
        
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
        
        # 解析回應和狀態
        response_lines = response.strip().split('\n')
        response_content = response_lines[0]
        
        # 更新狀態
        if len(response_lines) > 1 and "當前對話狀態:" in response_lines[-1]:
            new_state = response_lines[-1].split(': ')[1].strip()
            try:
                self.current_state = DialogueState(new_state)
            except ValueError:
                self.current_state = DialogueState.CONFUSED
        
        # 記錄 NPC 回應
        self.conversation_history.append(f"{self.character.name}: {response_content}")
        
        return f"{response_content}\n當前對話狀態: {self.current_state.value}"