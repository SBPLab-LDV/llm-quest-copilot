import asyncio
from src.core.character import Character
from src.core.dialogue import DialogueManager
from src.utils.logger import setup_logger

async def chat_with_npc():
    # 設定日誌
    logger = setup_logger('npc_chat')
    logger.info("開始NPC對話系統")

    # 創建角色實例
    character = Character(
        name="Elena",
        persona="一位剛動完手術的口腔癌患者",
        backstory="手術動完之後常常講話別人聽不懂，但還是試圖與醫護人員闡述自己的描述",
        goal="希望能夠與醫護人員溝通，讓他們了解自己的狀況"
    )
    
    # 創建對話管理器
    manager = DialogueManager(character)
    
    # 顯示歡迎訊息
    print(f"\n=== 與 {character.name} 對話 ===")
    print(f"角色背景: {character.persona}")
    print(f"目標: {character.goal}")
    print("\n輸入 'quit' 或 'exit' 結束對話")
    
    # 開始對話循環
    while True:
        try:
            # 獲取用戶輸入
            user_input = input("\n你: ").strip()
            
            # 檢查是否要結束對話
            if user_input.lower() in ['quit', 'exit']:
                print("\n結束對話")
                break
            
            # 如果輸入為空，繼續下一輪
            if not user_input:
                continue
            
            # 處理對話並獲取回應
            response = await manager.process_turn(user_input)
            
            # 顯示 NPC 回應
            print(f"\n{character.name}: {response}")
            
        except KeyboardInterrupt:
            print("\n使用者中斷對話")
            break
        except Exception as e:
            logger.error(f"對話過程發生錯誤: {e}")
            print(f"\n發生錯誤: {e}")
            break
    
    logger.info("結束NPC對話系統")

if __name__ == "__main__":
    asyncio.run(chat_with_npc()) 