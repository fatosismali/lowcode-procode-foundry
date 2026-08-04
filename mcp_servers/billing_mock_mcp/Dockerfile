FROM python:3.12-slim

WORKDIR /app

# Keep build logs ASCII-only (pip's Unicode progress bar breaks some log streamers)
ENV PIP_PROGRESS_BAR=off \
    PIP_NO_COLOR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY server.py .
COPY mock_data ./mock_data

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
EXPOSE 8000

CMD ["python", "server.py"]
