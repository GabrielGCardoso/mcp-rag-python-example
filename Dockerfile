FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ lib/
COPY scripts/ scripts/
COPY server.py sources.yaml ./

ENV PYTHONPATH=/app
ENV EMBED_BACKEND=ollama
ENV SQLITE_PATH=/data/index.sqlite
ENV MCP_TRANSPORT=streamable-http

CMD ["python", "server.py"]
