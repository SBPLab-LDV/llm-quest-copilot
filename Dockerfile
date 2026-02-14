# 使用 Python 3.11 作為基礎映像
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    python3-numpy \
    python3-scipy \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 複製專案文件
COPY requirements.txt .
COPY requirements-ui.txt .
COPY src/ ./src/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY recording.wav .
COPY run_ui.py .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-ui.txt \
    && pip install --no-cache-dir google-cloud-speech


# 設定環境變數
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露 FastAPI 與 Web UI 端口
EXPOSE 8000
EXPOSE 7860

# 複製啟動腳本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
