# docker/bot/Dockerfile
FROM python:3.11-slim

# System deps: PulseAudio + Chromium for Playwright
RUN apt-get update && apt-get install -y \
    pulseaudio \
    pulseaudio-utils \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

COPY bot/ ./bot/
COPY .env.example .env

RUN mkdir -p /data/transcripts

CMD ["python", "-m", "bot.main", "--help"]
