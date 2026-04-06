# Stage 1: Build frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: App (backend only)
FROM python:3.13-slim AS app
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends supervisor curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN mkdir -p /app/uploads /app/outputs /app/data

EXPOSE 8000

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

# Stage 3: Caddy with frontend assets
FROM caddy:2-alpine AS caddy
COPY --from=frontend-build /app/frontend/dist /srv/frontend
COPY Caddyfile /etc/caddy/Caddyfile
