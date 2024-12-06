import tkinter as tk
from src.gui.chat_window import ChatWindow
from src.utils.logger import setup_logger

def main():
    # 設定日誌
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

if __name__ == "__main__":
    main() 