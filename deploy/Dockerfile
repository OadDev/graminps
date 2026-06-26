# Production backend image for Gramin PAN Seva.
# Build context is the REPOSITORY ROOT (see docker-compose.yml -> context: ..).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install production dependencies (trimmed list, no dev/AI extras)
COPY deploy/requirements.txt /app/deploy/requirements.txt
RUN pip install --no-cache-dir -r /app/deploy/requirements.txt

# App code + static frontend (single-file Bootstrap app served by FastAPI)
COPY backend /app/backend
COPY frontend/public /app/frontend/public

WORKDIR /app/backend

# uploads dir for mocked FTP storage (mounted as a volume in compose)
RUN mkdir -p /app/backend/uploads

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
