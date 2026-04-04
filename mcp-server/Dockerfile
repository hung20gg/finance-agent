# Multi-stage build for optimized final image
FROM python:3.11-slim AS builder

# Install build dependencies if needed
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage - minimal runtime image
FROM python:3.11-slim

# Install only necessary runtime dependencies and clean up
RUN apt-get update && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app/keys /app/src && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Copy entrypoint script

# Update PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH
# Disable Python output buffering for real-time logs
ENV PYTHONUNBUFFERED=1
# Environment variable to control vectordb setup
ENV SETUP_VECTORDB_ON_START=false

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 9004)); s.close()"

# Run the entrypoint script
CMD ["python", "src/server.py", "--transport", "sse", "--host", "0.0.0.0", "--port", "9004"]
