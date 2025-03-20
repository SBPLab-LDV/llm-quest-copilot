# 使用 Python 3.9 作為基礎映像
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    python3-numpy \
    python3-scipy \
    && rm -rf /var/lib/apt/lists/*

# 複製專案文件
COPY requirements.txt .
COPY src/ ./src/
COPY config/ ./config/
COPY prompts/ ./prompts/
COPY run_tests.py .
COPY recording.wav .
COPY test_audio.wav .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 設定環境變數
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露 FastAPI 端口
EXPOSE 8000

# 啟動命令
CMD ["python", "-m", "src.api.server"] 