# Multi-stage build for optimized final image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Clone LLM repository if URL is provided
ARG LLM_REPO_URL=""
RUN if [ -n "$LLM_REPO_URL" ]; then \
        git clone "$LLM_REPO_URL" /build/llm; \
    fi

# Final stage - minimal runtime image
FROM python:3.11-slim

# Install only runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app/agent && \
    chown -R appuser:appuser /app

WORKDIR /app/agent

# Copy installed Python packages from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy LLM repository if it was cloned
COPY --from=builder /build/llm ./llm

# Copy agent code (excluding what's in .dockerignore)
COPY --chown=appuser:appuser . .

# Update PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# The agent is used as a library by backend service
# This container can also be used for testing
CMD ["python", "test_agent.py"]
