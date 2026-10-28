# Nortverse'i arkadaşla paylaşmak (Tailscale + giriş)

Site senin bilgisayarında çalışır. Arkadaşın internetten değil, ikinizin arasındaki şifreli Tailscale
bağlantısından girer. Siteye girmek için ayrıca kullanıcı adı + şifre gerekir.

Paylaşılan, **üretim sunucusudur** (`127.0.0.1:3000`, `scripts\frontend-supervisor` yönetir). Geliştirme
sunucusu (`npm run dev`, port 3001) hiç paylaşılmaz.

## Önce: üç kural

1. **Funnel kullanma.** `tailscale funnel` siteyi bütün internete açar. Sadece `tailscale serve` kullanılır
   (`paylasim-ac.bat` bunu yapar).
2. **Önce veritabanı portu.** Docker'daki PostgreSQL yalnızca bu bilgisayardan erişilebilir olmalı
   (`docker-compose.yml`: `127.0.0.1:5433:5432`). Kontrol (PowerShell):
   ```
   Get-NetTCPConnection -State Listen -LocalPort 5432,5433,8000,3000,3001 | Select LocalAddress, LocalPort
   ```
   `LocalAddress` her satırda `127.0.0.1` ya da `::1` olmalı. `0.0.0.0` ya da `::` görürsen paylaşmayı açma.
   (28 Ekim'de 5433 ve eski yerel PostgreSQL 5432 tüm arayüzlerde dinliyordu; 5433 Faz G'de düzeltiliyor.)
3. **Arkadaşın hesabı normal kullanıcı** (yönetici değil): her şeyi görür, ama yeni maç çekimi (tarayıcı
   açtıran ağır işler) tetikleyemez.

## Bir kez yapılacaklar

### Sen (site sahibi)
1. https://tailscale.com/download → Windows için indir, kur, Google hesabınla giriş yap.
2. Ağ profili: Tailscale bağdaştırıcısının profili PowerShell'de görünür:
   `Get-NetConnectionProfile | Select InterfaceAlias, NetworkCategory`. Tailscale satırı **Public** kalsın.
3. Tarayıcıda https://login.tailscale.com/admin/dns → **MagicDNS** ve **HTTPS Certificates** açık olsun
   (ilk açılışta "Enable HTTPS" düğmesi çıkar).
4. `scripts\paylasim-ac.bat` dosyasına çift tıkla → ekranda `https://<bilgisayar>.<ağ>.ts.net` adresi çıkar.
5. https://login.tailscale.com/admin/machines → bu bilgisayarın satırında **…** → **Share** → arkadaşının
   e-postasını yaz. (Arkadaşın sadece bu bilgisayarı görür, senin diğer cihazlarını görmez.)
6. **Erişim listesi (ACL): arkadaş sadece 443'e girebilsin.** https://login.tailscale.com/admin/acls →
   `"acls"` bölümünü şöyle yap (`100.x.y.z` = bu bilgisayarın Tailscale adresi, machines sayfasında yazar;
   e-postayı arkadaşınınkiyle değiştir):
   ```json
   "hosts": { "nortverse-pc": "100.x.y.z" },
   "acls": [
     { "action": "accept", "src": ["autogroup:member"], "dst": ["*:*"] },
     { "action": "accept", "src": ["arkadas@ornek.com"], "dst": ["nortverse-pc:443"] }
   ]
   ```
   İlk satır senin kendi cihazlarının birbirine erişimini korur; ikincisi arkadaşı yalnızca site portuna sınırlar.
7. Arkadaşına hesap aç (backend klasöründe) — **`--admin` olmadan**:
   ```
   python -m app.cli.main create-user <kullanici-adi>
   ```
   Ekrana çıkan şifreyi ona ilet.

### Arkadaşın
1. Tailscale'i kurar, kendi hesabıyla giriş yapar, gelen paylaşım davetini kabul eder.
2. 4. adımdaki `https://...ts.net` adresini açar, kullanıcı adı + şifresiyle girer.

### Birlikte bir kez test edin (arkadaşın bilgisayarında, PowerShell)
```
Test-NetConnection <bilgisayar>.<ağ>.ts.net -Port 443    # True olmalı
Test-NetConnection <bilgisayar>.<ağ>.ts.net -Port 5433   # False olmalı
Test-NetConnection <bilgisayar>.<ağ>.ts.net -Port 5432   # False
Test-NetConnection <bilgisayar>.<ağ>.ts.net -Port 8000   # False
Test-NetConnection <bilgisayar>.<ağ>.ts.net -Port 3000   # False
Test-NetConnection <bilgisayar>.<ağ>.ts.net -Port 3001   # False
```
443 dışında `True` çıkan varsa paylaşımı kapat (`paylasim-kapat.bat`) ve bana yaz.

Canlı sayfa (`/canli`) sağ üstte "WS" göstermeli. "REST" görünüyorsa WebSocket Tailscale üzerinden geçmiyor
demektir; sen şunu bir kez çalıştır:
```
tailscale serve --bg --set-path /ws http://127.0.0.1:8000/ws
```

## Her gün
- Site senin bilgisayarında açık olmalı (`Nortverse Başlat` kısayolu ya da "Frontend" + "Backend" görevleri).
  PC kapalıyken arkadaşın giremez.
- Paylaşımı kapatmak: `scripts\paylasim-kapat.bat`.
- Frontend kodunu değiştirdikten sonra: `scripts\frontend-build.bat` (derleme başarısızsa eski sürüm çalışmaya
  devam eder; başarılıysa site birkaç saniye içinde yeni sürüme geçer).

## Hesaplar
- Hesapları listele: `python -m app.cli.main list-users`
- Şifre değiştir (o hesabın açık oturumları kapanır): `python -m app.cli.main set-password <kullanici-adi>`
- Çok fazla hatalı denemeyle kilitlenen giriş (kullanıcı başına 8, toplam 40 hata / 15 dk):
  `python -m app.cli.main unlock <kullanici-adi>` ya da hepsi için `unlock --all`
- `--admin` hesabı yeni maç çekimi gibi kaynağa yük bindiren işleri de tetikleyebilir — sadece sende olsun.
