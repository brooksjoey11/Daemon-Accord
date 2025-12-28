# Execution Engine Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

    # Install Playwright and browsers
RUN pip install --no-cache-dir playwright==1.40.0 && \
    playwright install chromium

# Install browser dependencies manually (playwright install-deps has font issues)
RUN apt-get update && apt-get install -y \
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
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# Create requirements.txt if it doesn't exist (using common dependencies)
RUN echo "playwright>=1.40.0" > requirements.txt && \
    echo "redis>=5.0.1" >> requirements.txt && \
    echo "asyncpg>=0.29.0" >> requirements.txt && \
    echo "sqlmodel>=0.0.14" >> requirements.txt && \
    echo "fastapi>=0.104.0" >> requirements.txt && \
    echo "uvicorn[standard]>=0.24.0" >> requirements.txt && \
    echo "pydantic>=2.5.0" >> requirements.txt && \
    echo "structlog>=25.0.0" >> requirements.txt && \
    echo "backoff>=2.2.0" >> requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create artifacts directory
RUN mkdir -p /app/artifacts

# Expose port
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MAX_BROWSERS=20

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import redis; r = redis.Redis.from_url('redis://redis:6379/0'); r.ping()" || exit 1

# Start the worker
CMD ["python", "src/worker.py"]

