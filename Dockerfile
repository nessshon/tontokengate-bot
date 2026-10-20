FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/nessshon/tontokengate-bot" \
      org.opencontainers.image.description="Telegram bot that grants access to private chats by TON jettons and NFTs." \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app"]
