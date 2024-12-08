import asyncio
from src.core.dialogue import DialogueManager
from src.utils.config import load_character, list_available_characters, load_config
from src.utils.logger import setup_logger
from src.utils.speech_input import SpeechInput
from typing import Optional
import keyboard

async def get_user_input(speech_input: Optional[SpeechInput] = None, input_mode: str = 'text') -> str:
    """獲取使用者輸入，支援文字或語音"""
    if input_mode == 'voice' and speech_input:
        print("\n請按住 space 鍵開始錄音，放開結束錄音...")
        print("(或輸入 'q' 離開系統)")
        
        while True:
            # 檢查是否要退出
            event = keyboard.read_event(suppress=True)
            if event.event_type == 'down' and event.name == 'q':
                return 'quit'
            elif event.event_type == 'down' and event.name == 'space':
                text = speech_input.record_audio(key='space')
                if text:
                    print(f"\n護理人員 (語音輸入): {text}")
                    return text
                
                print("\n語音辨識失敗")
                choice = input("是否切換到文字輸入？(y/n，預設n): ").lower()
                if choice == 'y':
                    return input("\n護理人員 (文字輸入): ").strip()
                print("\n繼續使用語音輸入...")
                print("\n請按住 space 鍵開始錄音，放開結束錄音...")
                print("(或輸入 'q' 離開系統)")
    else:
        return input("\n護理人員: ").strip()

async def chat_with_npc():
    # 設定日誌
    logger = setup_logger('npc_chat')
    logger.info("開始NPC對話系統")

    # 載入設定
    config = load_config()
    input_mode = config['input_mode']
    
    # 如果使用語音輸入，初始化語音輸入模組
    speech_input = None
    if input_mode == 'voice':
        save_recordings = config.get('save_recordings', False)
        debug_mode = config.get('debug_mode', False)
        speech_input = SpeechInput(
            config['google_api_key'],
            save_recordings=save_recordings,
            debug_mode=debug_mode
        )

    # 顯示可用角色列表
    characters = list_available_characters()
    print("\n=== 可選擇的病患 ===")
    print("\n請選擇要對話的病患：")
    
    # 建立編號對應表
    char_mapping = {}
    for i, (char_id, char_data) in enumerate(characters.items(), 1):
        char_mapping[str(i)] = char_id
        print(f"\n[{i}] {char_data['name']}")
        print(f"    背景: {char_data['persona']}")
        print(f"    狀況: {char_data['backstory']}")

    # 讓使用者選擇角色
    while True:
        choice = input("\n請輸入病患編號 (或輸入 'q' 退出): ").strip().lower()
        if choice == 'q':
            print("\n結束程式")
            return
        if choice in char_mapping:
            char_id = char_mapping[choice]
            break
        print("無效的選擇，請重新輸入")

    # 載入選擇的角色
    character = load_character(char_id)
    
    # 創建對話管理器
    manager = DialogueManager(character)
    
    # 顯示歡迎訊息
    print(f"\n=== 開始與 {character.name} 對話 ===")
    print(f"病患背景: {character.persona}")
    print(f"目標: {character.goal}")
    print("\n您現在可以開始對話")
    print("(輸入 'quit' 或 'exit' 結束對話)")
    
    # 開始對話循環
    while True:
        try:
            # 獲取用戶輸入
            user_input = await get_user_input(speech_input, input_mode)
            
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