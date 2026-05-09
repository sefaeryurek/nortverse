FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Container ayağa kalkmadan önce schema migration koş.
# alembic env.py DATABASE_URL'den sync URL'i otomatik üretir (asyncpg → psycopg2).
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
