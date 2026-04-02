FROM python:3.11-slim

WORKDIR /app

# Install Python deps
RUN pip install --no-cache-dir pandas>=2.0 requests>=2.28 tornado>=6.1

# Copy source
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Persistent data volume
RUN mkdir -p /app/backend/data
VOLUME ["/app/backend/data"]

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["python3", "run.py"]
