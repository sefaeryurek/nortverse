FROM mcr.microsoft.com/playwright/python:v1.47.0-noble

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()"

COPY . .

# Uygulama yeni şemayı gerektirir; migration başarısızsa başlatma da başarısız olsun.
CMD ["sh", "-c", "alembic upgrade head && exec python -m uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
