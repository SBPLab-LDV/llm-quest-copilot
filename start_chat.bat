@echo off
:: 啟動 Anaconda 環境
call D:\anaconda3\Scripts\activate.bat
:: 切換到指定的環境（請將 your_env_name 改為你的環境名稱）
@REM call conda activate your_env_name
:: 執行程式
python gui_main.py
pause 