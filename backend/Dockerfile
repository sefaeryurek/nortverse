FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary ve lxml wheel'leri için gerekli minimal sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Container ayağa kalkmadan önce schema migration koş.
# alembic env.py DATABASE_URL'den sync URL'i otomatik üretir (asyncpg → psycopg2).
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
