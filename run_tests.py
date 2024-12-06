import asyncio
from src.core.dialogue import DialogueManager
from src.utils.config import load_character
from src.tests.test_runner import NPCScenarioTester

async def run_tests():
    # 載入預設測試角色 (使用 ID "1" 代替 "elena")
    character = load_character('1')
    
    # 創建對話管理器
    manager = DialogueManager(character)
    
    # 創建測試器並運行測試
    tester = NPCScenarioTester(manager)
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(run_tests()) 