FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt -v

# 复制应用代码和测试脚本
COPY app.py index.html test_install.py ./
RUN mkdir -p /app/downloads

ENV DOWNLOAD_DIR=/app/downloads \
    PORT=8787

EXPOSE 8787
VOLUME ["/app/downloads"]

# 先运行测试脚本，然后启动应用
CMD ["python", "-c", "import test_install; print('\\n=== 启动应用 ==='); import app"]