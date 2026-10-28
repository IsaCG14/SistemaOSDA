# Backend FastAPI - Dockerfile

# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=900 --retries 5 torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --timeout=900 --retries 5 -r requirements.txt

# Production stage
FROM python:3.12-slim as production

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=900 --retries 5 torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --timeout=900 --retries 5 -r requirements.txt

# Copy application code
COPY . .

# Ensure alembic.ini is in app directory for runtime
RUN cp /app/alembic.ini /app/app/alembic.ini

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Development stage
FROM production as development

USER root
RUN pip install --no-cache-dir watchdog
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Migrator stage
FROM production as migrator

USER root
# Alembic already installed via requirements.txt, just run migrations
CMD ["python", "-m", "alembic", "upgrade", "head"]