# Multi-stage build for production container

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 agent

# Copy installed packages from builder
COPY --from=builder /root/.local /home/agent/.local

# Copy application
COPY --chown=agent:agent src/ ./src/
COPY --chown=agent:agent .env.example ./.env

# Set environment
ENV PATH=/home/agent/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; print('healthy')" || exit 1

# Run
ENTRYPOINT ["python", "-m", "src.orchestrator"]