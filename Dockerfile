FROM python:3.12-slim

WORKDIR /app

# System deps: curl for healthcheck, ca-certs for TLS to Telegram + OpenAI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Python deps (separate layer for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY *.py ./

# All existing data: messages, IOCs, keywords, state, chat history, watchlists
COPY telegram_intel/ telegram_intel/

# Pre-authenticated Telegram session files (no re-login needed on server)
COPY *.session ./

# telegram_intel is a persistent volume — new data accumulates here after start
# Docker seeds the volume from the COPY'd layer on first run
VOLUME ["/app/telegram_intel"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

CMD ["python", "orchestrator.py"]
