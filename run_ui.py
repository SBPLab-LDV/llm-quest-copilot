#!/usr/bin/env python
"""
醫護對話系統 UI 啟動腳本
"""
import os
import sys
import argparse
import traceback
import gradio as gr

def main():
    """主程序"""
    try:
        print("Starting UI application...")
        
        # 解析命令行參數
        parser = argparse.ArgumentParser(description="醫護對話系統 UI")
        parser.add_argument(
            "--api-url", 
            default="http://0.0.0.0:8000",
            help="API 服務器的 URL"
        )
        parser.add_argument(
            "--port", 
            type=int, 
            default=7860,
            help="UI 服務器的埠號"
        )
        parser.add_argument(
            "--host", 
            default="0.0.0.0",
            help="UI 服務器的主機地址"
        )
        parser.add_argument(
            "--share", 
            action="store_true",
            help="是否創建公共分享連結"
        )
        parser.add_argument(
            "--debug", 
            action="store_true",
            help="是否啟用調試模式"
        )
        
        args = parser.parse_args()
        
        print(f"Importing app module...")
        from src.ui.app import create_app
        
        print(f"Creating app with API URL: {args.api_url}")
        app = create_app(api_url=args.api_url)
        
        print(f"啟動醫護對話系統 UI，連接到 API 伺服器: {args.api_url}")
        print(f"UI 伺服器運行於: http://{args.host}:{args.port}")
        if args.share:
            print("正在創建公共分享連結...")
        
        # 啟動應用
        print("Launching app...")
        app.launch(
            server_name=args.host,
            server_port=args.port,
            share=args.share,
            debug=args.debug
        )
    except Exception as e:
        print(f"Error starting UI: {e}")
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main()) 