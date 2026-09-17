FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- final stage: sadece runtime ---
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY . .

# Playwright Python paketi tarayıcı ikilisini kurmaz; fixture ve analiz scraper'ı Chromium gerektirir.
RUN python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Uygulama yeni şemayı gerektirir; migration başarısızsa başlatma da başarısız olsun.
CMD ["sh", "-c", "alembic upgrade head && exec python -m uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
