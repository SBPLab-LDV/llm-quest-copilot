import tkinter as tk
import argparse
from src.gui.chat_window import ChatWindow
from src.utils.logger import setup_logger
from src.core.dialogue import DialogueManager
from src.utils.config import load_character, list_available_characters
import asyncio

async def terminal_mode():
    """終端機模式"""
    logger = setup_logger('npc_chat_cli')
    logger.info("開始NPC對話系統 (終端機版)")
    
    try:
        # 顯示可用的病患列表
        print("\n=== 可用的病患列表 ===")
        characters = list_available_characters()
        for char_id, char_data in characters.items():
            print(f"\n[{char_id}]")
            print(f"名稱: {char_data['name']}")
            print(f"背景: {char_data['persona']}")
            print(f"狀況: {char_data['backstory']}")
        
        # 選擇病患
        while True:
            char_id = input("\n請輸入病患ID: ").strip()
            if char_id in characters:
                break
            print("無效的病患ID，請重試")
        
        # 載入病患並初始化對話管理器
        character = load_character(char_id)
        dialogue_manager = DialogueManager(character, use_terminal=True)
        
        print(f"\n=== 開始與 {character.name} 對話 ===")
        print(f"背景: {character.persona}")
        print(f"目標: {character.goal}")
        print("\n提示：")
        print("- 輸入 'q' 或 'quit' 或 'exit' 結束對話")
        print("- 在選項中按 '0' 跳過當前回應")
        print("- 按 1-5 選擇對應的回應選項\n")
        
        # 開始對話循環
        while True:
            user_input = input("\n護理人員: ").strip()
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
                
            # 獲取並顯示回應
            response = await dialogue_manager.process_turn(user_input)
            if response == "quit":
                break
            elif response:  # 如果有回應（不是跳過）
                print(f"\n{character.name}: {response}")
                print(f"[當前狀態: {dialogue_manager.current_state.value}]")
    
    except Exception as e:
        logger.error(f"程式執行時發生錯誤: {e}")
        raise
    finally:
        logger.info("結束NPC對話系統")

def gui_mode():
    """GUI模式"""
    logger = setup_logger('npc_chat_gui')
    logger.info("開始NPC對話系統 (GUI版)")

    try:
        # 創建主視窗
        root = tk.Tk()
        
        # 設定視窗圖示和標題
        root.title("口腔癌病患對話系統")
        
        # 創建聊天視窗
        app = ChatWindow(root)
        
        # 啟動主循環
        root.mainloop()
        
    except Exception as e:
        logger.error(f"程式執行時發生錯誤: {e}")
        raise
    finally:
        logger.info("結束NPC對話系統")

def main():
    # 解析命令行參數
    parser = argparse.ArgumentParser(description='口腔癌病患對話系統')
    parser.add_argument('--terminal', '-t', action='store_true',
                      help='使用終端機模式（預設為GUI模式）')
    args = parser.parse_args()
    
    if args.terminal:
        # 終端機模式
        asyncio.run(terminal_mode())
    else:
        # GUI模式
        gui_mode()

if __name__ == "__main__":
    main() 