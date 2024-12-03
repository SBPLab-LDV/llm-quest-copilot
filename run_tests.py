import asyncio
from src.core.character import Character
from src.core.dialogue import DialogueManager
from src.tests.test_runner import NPCScenarioTester

async def run_tests():
    # 創建角色實例
    character = Character(
        name="Elena",
        persona="一位剛動完手術的口腔癌患者",
        backstory="手術動完之後常常講話別人聽不懂，但還是試圖與醫護人員闡述自己的描述",
        goal="希望能夠與醫護人員溝通，讓他們了解自己的狀況"
    )
    
    # 創建對話管理器
    manager = DialogueManager(character)
    
    # 創建測試器並運行測試
    tester = NPCScenarioTester(manager)
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(run_tests()) 