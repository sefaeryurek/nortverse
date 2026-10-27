# Nortverse'i arkadaşla paylaşmak (Tailscale + giriş)

Site senin bilgisayarında çalışır. Arkadaşın internetten değil, ikinizin arasındaki şifreli Tailscale
bağlantısından girer. Siteye girmek için ayrıca kullanıcı adı + şifre gerekir.

## Bir kez yapılacaklar

### Sen (site sahibi)
1. https://tailscale.com/download → Windows için indir, kur, Google hesabınla giriş yap.
2. Tarayıcıda https://login.tailscale.com/admin/dns → **MagicDNS** ve **HTTPS Certificates** açık olsun
   (ilk açılışta "Enable HTTPS" düğmesi çıkar).
3. `scripts\paylasim-ac.bat` dosyasına çift tıkla → ekranda `https://<bilgisayar>.<ağ>.ts.net` adresi çıkar.
4. https://login.tailscale.com/admin/machines → bu bilgisayarın satırında **…** → **Share** → arkadaşının
   e-postasını yaz. (Arkadaşın sadece bu bilgisayarı görür, senin diğer cihazlarını görmez.)
5. Arkadaşına hesap aç (backend klasöründe):
   ```
   python -m app.cli.main create-user <kullanici-adi> --admin
   ```
   Ekrana çıkan şifreyi ona ilet.

### Arkadaşın
1. Tailscale'i kurar, kendi hesabıyla giriş yapar, gelen paylaşım davetini kabul eder.
2. 3. adımdaki `https://...ts.net` adresini açar, kullanıcı adı + şifresiyle girer.

## Her gün
- Site senin bilgisayarında açık olmalı (`Nortverse Başlat` kısayolu). PC kapalıyken arkadaşın giremez.
- Paylaşımı kapatmak: `scripts\paylasim-kapat.bat`.

## Hesaplar
- Hesapları listele: `python -m app.cli.main list-users`
- Şifre değiştir (o hesabın açık oturumları kapanır): `python -m app.cli.main set-password <kullanici-adi>`
- `--admin` hesabı yeni maç çekimi gibi kaynağa yük bindiren işleri de tetikleyebilir.
