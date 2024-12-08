@echo off
:: 啟動 Anaconda 環境
call D:\anaconda3\Scripts\activate.bat
:: 執行程式（使用 pythonw 避免顯示終端機視窗）
start pythonw gui_main.py 