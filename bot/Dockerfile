# Bot Telegram - Dockerfile

# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim as production

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot/ .

# Copy shared app modules from backend
COPY backend/app ./app

# Copy entrypoint (as root before switching user)
COPY bot/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check - just check if python process is running (polling mode)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pgrep -f "python.*bot.main" >/dev/null || exit 1

EXPOSE 8081

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "bot.main", "--webhook"]

# Development stage
FROM production as development

USER root
RUN pip install --no-cache-dir watchdog
USER appuser

CMD ["python", "-m", "bot.main", "--polling"]