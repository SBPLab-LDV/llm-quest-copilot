#!/bin/sh
# 啟動 FastAPI（8000）到背景
python -m src.api.server &

# 啟動 Web UI（7860）
python3 run_ui.py --port 7860
