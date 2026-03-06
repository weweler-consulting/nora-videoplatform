# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.12-slim
WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY seed.py ./seed.py
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

CMD ["./start.sh"]
