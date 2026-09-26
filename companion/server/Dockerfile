FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY companion/server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY companion /app/companion

ENV COMPANION_HOST=0.0.0.0
ENV COMPANION_PORT=8000
ENV COMPANION_DATA_DIR=/app/data
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "companion.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
