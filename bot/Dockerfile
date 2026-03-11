FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright and Xvfb (virtual display for DOM rendering)
RUN apt-get update && apt-get install -y \
    wget curl \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers to a world-readable location
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium && chmod -R 755 /ms-playwright

# Copy bot source
COPY . /app/bot
COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "bot.main"]
