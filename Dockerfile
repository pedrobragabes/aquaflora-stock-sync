# AquaFlora Stock Sync - Dockerfile
# Optimized for production deployment

FROM python:3.11-slim

# Labels
LABEL org.opencontainers.image.title="AquaFlora Stock Sync"
LABEL org.opencontainers.image.description="Stock synchronization between Athos ERP and WooCommerce"
LABEL org.opencontainers.image.version="2.0"

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 -m appuser

# Install curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories and set ownership
RUN mkdir -p data/input data/output logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose dashboard port
EXPOSE 8080

# Default: run dashboard
CMD ["python", "-m", "uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8080"]
