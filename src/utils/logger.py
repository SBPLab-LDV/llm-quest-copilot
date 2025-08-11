import logging
from datetime import datetime
import os

def setup_logger(name: str) -> logging.Logger:
    """設置日誌記錄器"""
    # 確保日誌目錄存在
    os.makedirs('logs', exist_ok=True)
    
    # 創建日誌記錄器
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 設定檔案處理器
    log_file = f"logs/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 設定控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 設定格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加處理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger 