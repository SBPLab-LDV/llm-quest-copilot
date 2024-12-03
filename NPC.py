import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime
import google.generativeai as genai
import json
import os
import re
# 設定
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'AIzaSyAfjRGMGWSXn7Kf6qnj4IQezhXh1ZaeLJ0')
genai.configure(api_key=GOOGLE_API_KEY)
# 初始化 Gemini 模型
model = genai.GenerativeModel('gemini-1.5-flash')
# 定義新的狀態和任務枚舉
class DialogueState(Enum):
    ON_TRACK = "on_track"
    DEVIATED = "deviated"
    TRANSITIONING = "transitioning"
class TaskStage(Enum):
    INITIAL = "initial"
    SUBTASK = "subtask"
@dataclass
class DialogueTurn:
    speaker: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    subtask_levels: List[int] = field(default_factory=list)
@dataclass
class Character:
    name: str
    persona: str
    backstory: str
    goal: str
    #dialogue_templates: Dict[TaskStage, List[str]]
@dataclass
class DialogueContext:
    current_task: TaskStage
    current_state: DialogueState
    dialogue_history: List[DialogueTurn]
    subtask_levels: List[int] = field(default_factory=list)
class DialogueManager:
    def __init__(self, character: Character):
        self.character = character
        self.context = DialogueContext(
            current_task=TaskStage.INITIAL,
            current_state=DialogueState.ON_TRACK,
            dialogue_history=[],
            subtask_levels=[0]
        )
        self.chat_history = model.start_chat(history=[])
    async def process_turn(self, user_input: str) -> str:
        # 記錄玩家的輸入，包含當前子任務層級
        turn = DialogueTurn(
            speaker="user",
            content=user_input,
            subtask_levels=self.context.subtask_levels.copy()
        )
        self.context.dialogue_history.append(turn)
        # 生成給 Gemini 的提示語
        prompt = self._create_prompt(user_input)
        # 使用 Gemini 生成回應
        response = await asyncio.to_thread(
            lambda: model.generate_content(prompt).text
        )
        # 處理多重回答的情況
        responses = self._parse_multiple_responses(response)
        # 格式化回答
        formatted_response = self._format_responses(responses)
        # 記錄助手的回應
        patient_turn = DialogueTurn(
            speaker="patient",
            content=response,
            subtask_levels=self.context.subtask_levels.copy()
        )
        self.context.dialogue_history.append(patient_turn)
        # 更新對話上下文
        context_update = await self._update_dialogue_context(user_input)
        # 將當前狀態信息附加到回應中
        state_info = self._get_current_state_description()
        full_response = f"{response}\n\n{state_info}"
        return full_response.strip()
    def _parse_multiple_responses(self, response: str) -> List[str]:
        """
        解析多重回答
        支持的格式：
明確的編號清單
多行文本
以 "選項1："、"選項2："開頭的格式
        """
        # 嘗試解析編號清單
        numbered_list_pattern = r'^\d+\.\s*(.+)$'
        numbered_matches = re.findall(numbered_list_pattern, response, re.MULTILINE)
        if numbered_matches:
            return numbered_matches
        # 嘗試解析 "選項X：" 格式
        option_pattern = r'選項\d+：\s*(.+)'
        option_matches = re.findall(option_pattern, response)
        if option_matches:
            return option_matches
        # 預設分割策略：按換行和特定分隔符號
        split_patterns = [
            r'\n\s*\n',  # 多個換行
            r'\n-\s*',   # 以 - 開頭的行
            r'\n•\s*'    # 以 • 開頭的行
        ]
        for pattern in split_patterns:
            matches = re.split(pattern, response)
            matches = [m.strip() for m in matches if m.strip()]
            if len(matches) > 1:
                return matches
        # 如果無法分割，返回原始回應
        return [response]
    def _format_responses(self, responses: List[str]) -> str:
        """
        格式化多重回答為條列式
        """
        if len(responses) == 1:
            return responses[0]
        formatted = "多重選項回答：\n"
        for i, resp in enumerate(responses, 1):
            formatted += f"{i}. {resp}\n"
        return formatted.strip()
    async def _update_dialogue_context(self, user_input: str) -> Dict:
        # 格式化對話歷史
        formatted_history = "\n".join([
            f"[Level {'.'.join(map(str, turn.subtask_levels))}] "
            f"{turn.speaker.upper()}: {turn.content}"
            for turn in self.context.dialogue_history
        ])
        context_prompt = f"""
        完整對話歷史:
        {formatted_history}
        當前對話情境：
當前任務階段: {self.context.current_task.value}
當前對話狀態: {self.context.current_state.value}
子任務層級: {self.context.subtask_levels}
        醫護人員輸入: {user_input}
        請返回以下格式的 JSON，描述下一步：
        {{
            "next_state": "ON_TRACK/DEVIATED/TRANSITIONING",
        }}
        注意：
ON_TRACK 表示還在原本的話題中
DEVIATED 表示醫護人員說出肯定句或者結尾與，例如好、我等等幫你看、我請醫生過來、謝謝、不會等
TRANSITIONING 表示有新的問題與前一個回答有關
若任務階段為INITIAL，則醫護人員提出任何問題時，next_state必為TRANSITIONING
當任務階段為SUBTASK，且醫護人員提出與前一個回答或者前一個問題無關的問題時，next_state必為DEVIATED
        """
        try:
            result = await asyncio.to_thread(
                lambda: model.generate_content(context_prompt).text
            )
            #print(result)
            # 提取 JSON
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                result = json_match.group(0)
            updates = json.loads(result)
            # 根據當前任務階段和狀態進行邏輯處理
            if self.context.current_task == TaskStage.INITIAL:
                if updates.get("next_state") == "ON_TRACK":
                    # 進入第一層子任務
                    self.context.current_task = TaskStage.SUBTASK
                    self.context.subtask_levels[0] += 1
            elif self.context.current_task == TaskStage.SUBTASK:
                if updates.get("next_state") == "TRANSITIONING":
                    # 返回 INITIAL 階段並重置子任務層級
                    self.context.current_task = TaskStage.INITIAL
                    self.context.subtask_levels = [0]
                    self.context.dialogue_history.clear()
                elif updates.get("next_state") == "ON_TRACK":
                    # 根據當前層級決定操作
                    current_depth = len(self.context.subtask_levels)
                    # 如果最後一層小於目前深度，增加最後一層
                    self.context.subtask_levels[-1] += 1
            # 更新對話狀態
            self.context.current_state = DialogueState[updates.get("next_state", "ON_TRACK")]
            return updates
        except Exception as e:
            print(f"解析 Gemini 回應時發生錯誤: {str(e)}")
            # 發生錯誤時保持當前狀態
            return {}
    def _create_prompt(self, user_input: str) -> str:
        # 格式化對話歷史
        formatted_history = "\n".join([
            f"[Level {'.'.join(map(str, turn.subtask_levels))}] "
            f"{turn.speaker.upper()}: {turn.content}"
            for turn in self.context.dialogue_history[:-1]  # Exclude the latest turn
        ])
        return f"""
        完整對話歷史:
        {formatted_history}
        你是 {self.character.name}，一個 {self.character.persona}。
        你的背景故事: {self.character.backstory}
        當前對話上下文:
任務階段: {self.context.current_task.value}
對話狀態: {self.context.current_state.value}
子任務層級: {self.context.subtask_levels}
        請以 {self.character.name} 的身份回應以下對話:
        醫護人員說: {user_input}
        請以不超過十個字的內容回答
        注意事項:
保持在角色設定範圍內
回應要簡潔自然(不超過15個字)
        """
    def _get_current_state_description(self) -> str:
        subtask_description = ".".join(map(str, self.context.subtask_levels))
        return f"""
        [對話系統信息]
        :label: 當前任務階段: {self.context.current_task.value}
        :star2: 當前對話狀態: {self.context.current_state.value}
        :1234: 子任務層級: {subtask_description}
        """
async def main():
    # 創建一個角色實例
    character = Character(
        name="Elena",
        persona="一位剛動完手術的口腔癌患者",
        backstory="手術動完之後常常講話別人聽不懂，但還是試圖與醫護人員闡述自己的描述",
        goal="希望能夠與醫護人員溝通，讓他們了解自己的狀況"
    )
    # 創建對話管理器
    manager = DialogueManager(character)
    print("=== 對話系統 ===")
    print("輸入 'quit' 來結束對話。")
    # 對話循環
    while True:
        user_input = input("\n你: ")
        if user_input.lower() == 'quit':
            print("結束對話...")
            break
        try:
            response = await manager.process_turn(user_input)
            print(f"\n病患: \n{response}")
        except Exception as e:
            print(f"\n系統錯誤: {str(e)}")
            print("請重試...")
if __name__ == "__main__":
    asyncio.run(main())
