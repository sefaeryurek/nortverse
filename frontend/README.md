# Nortverse frontend

Next.js arayüzü FastAPI backend'inden maç, sonuç ve analiz verisi alır.

## Yerel çalıştırma

Önce `backend/` dizininde veritabanı ayarlarını yapıp migration'ları uygulayın ve API'yi başlatın:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.cli.main serve
```

Ardından `frontend/.env.local` dosyasında `BACKEND_URL=http://localhost:8000` kullanın ve ayrı terminalde:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

`BACKEND_URL` Next.js sunucusunun `/api/*` isteklerini backend'e yönlendirmesini sağlar. Tarayıcı aynı origin üzerinden istek gönderir. `NEXT_PUBLIC_API_URL` tarayıcıyı doğrudan verilen adrese yönlendirir; bunu yalnızca doğrudan erişim ve CORS yapılandırması gerekiyorsa kullanın.

## Kontroller

```powershell
npm.cmd run test:run
npm.cmd run lint
npx.cmd tsc --noEmit
npm.cmd run build
```
