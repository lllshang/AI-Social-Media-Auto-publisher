FROM python:3.11-slim

WORKDIR /app

# 国内服务器构建加速（腾讯云等）
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|deb.debian.org|mirrors.tencent.com|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's|deb.debian.org|mirrors.tencent.com|g' /etc/apt/sources.list; \
    fi

# 系统 Chromium（走 apt 国内源，无需下载 Playwright 167MB 包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    libxcb1 libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libasound2 \
    chromium \
    && rm -rf /var/lib/apt/lists/*

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

RUN mkdir -p /data/materials /data/cookies /opt/playwright

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
