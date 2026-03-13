FROM python:3.12-slim

WORKDIR /app

# System deps: curl for healthcheck, ca-certs for TLS, libreoffice for PDF conversion, tor for dark web
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libreoffice-writer tor && rm -rf /var/lib/apt/lists/*

# Tor configuration: SOCKS5 on 9050, Control on 9051, no exit relay
RUN echo "SocksPort 9050" > /etc/tor/torrc && \
    echo "ControlPort 9051" >> /etc/tor/torrc && \
    echo "CookieAuthentication 0" >> /etc/tor/torrc && \
    echo "HashedControlPassword " >> /etc/tor/torrc && \
    echo "ExitRelay 0" >> /etc/tor/torrc && \
    echo "ExitPolicy reject *:*" >> /etc/tor/torrc

# Python deps (separate layer for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY *.py ./
COPY app/ app/

# Report template and branding assets
COPY scanwave_report_template.docx ./
COPY scanwave_logo.png ./

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

# Run migration (idempotent) then start the platform
CMD ["sh", "-c", "python migrate.py && python orchestrator.py"]
