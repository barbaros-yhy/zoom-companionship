FROM python:3.11-slim

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
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps || playwright install chromium

COPY bot/ ./bot/

RUN mkdir -p /data/transcripts

# No CMD — bot is started per-meeting via the API/orchestration layer
# Run with: docker run ... python -m bot.main --meeting-url URL --meeting-id ID
ENTRYPOINT ["python", "-m", "bot.main"]
