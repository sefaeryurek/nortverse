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

# Migration başarısız olsa bile API başlasın (DB geçici erişilmez olabilir).
CMD ["sh", "-c", "alembic upgrade head || echo 'Migration atlandı'; exec python -m uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
