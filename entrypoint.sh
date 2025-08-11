#!/bin/sh
# 啟動 FastAPI（8000）到背景
python -m src.api.server &

# 再啟動你的另一個 Python 程式（7860）
python3 run_ui.py --port 7860
