FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib/ lib/
COPY scripts/ scripts/
COPY fcc_docs/ fcc_docs/
COPY server.py .

ENV PYTHONPATH=/app
ENV DOCS_DIR=fcc_docs

CMD ["python", "server.py"]
