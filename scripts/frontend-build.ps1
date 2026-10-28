# Nortverse - Frontend uretim derlemesi (Sprint 94 E6).
# Calistirma: scripts\frontend-build.bat  (kod degisikliginden sonra; pencereli ya da gorevle)
#
# Iki yuva: frontend\.next-prod-a ve frontend\.next-prod-b. Calisan sunucu frontend\.prod-slot dosyasindaki
# yuvayi kullanir. Derleme her zaman BOSTAKI yuvaya yapilir:
# - basarisizsa calisan surum hic etkilenmez (uyari + log, kod 1)
# - basariliysa .prod-slot yeni yuvaya cevrilir; frontend denetleyicisi bunu en gec 15 sn icinde gorup
#   sunucuyu yeni yuvayla yeniden baslatir (birkac saniyelik kesinti)
# Gelistirme sunucusu (npm run dev, port 3001) varsayilan .next dizinini kullanir; bu derleme ona dokunmaz.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$front = Join-Path $root "frontend"
$logs = Join-Path $root "scripts\logs"
$buildLog = Join-Path $logs "frontend-build.log"
$startsLog = Join-Path $logs "frontend_starts.log"
$slotFile = Join-Path $front ".prod-slot"
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Force $logs | Out-Null }

function Note([string]$message) {
    Add-Content -Path $startsLog -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message) -Encoding UTF8
    Write-Host $message
}

$mutex = New-Object System.Threading.Mutex($false, "Local\NortverseFrontendBuild")
if (-not $mutex.WaitOne(0)) { Write-Host "Baska bir frontend derlemesi suruyor."; exit 0 }

$active = if (Test-Path $slotFile) { (Get-Content $slotFile -Raw).Trim() } else { "" }
$target = if ($active -eq "a") { "b" } else { "a" }
$dist = ".next-prod-$target"
$distPath = Join-Path $front $dist

Note ("Derleme basliyor: {0} (calisan yuva: {1})" -f $dist, $(if ($active) { $active } else { "yok" }))
if (Test-Path $distPath) { Remove-Item -Recurse -Force $distPath -ErrorAction SilentlyContinue }

$env:NEXT_DIST_DIR = $dist
$env:NEXT_TELEMETRY_DISABLED = "1"
Push-Location $front
& cmd.exe /c ("npx next build > ""{0}"" 2>&1" -f $buildLog)
$code = $LASTEXITCODE
Pop-Location

if ($code -ne 0 -or -not (Test-Path (Join-Path $distPath "BUILD_ID"))) {
    Note ("Derleme BASARISIZ (kod {0}) - calisan surum korunuyor. Ayrinti: {1}" -f $code, $buildLog)
    if ($env:NORTVERSE_NO_NOTIFY -ne "1") {  # sadece deneme icin kapatilir
        & cmd.exe /c ('"{0}" "{1}"' -f (Join-Path $root "scripts\notify-error.bat"), `
            "Frontend derlemesi basarisiz - calisan surum korunuyor. scripts\logs\frontend-build.log") | Out-Null
    }
    exit 1
}

Set-Content -Path $slotFile -Value $target -Encoding ASCII -NoNewline
Note ("Derleme tamam: yuva {0} etkin; denetleyici sunucuyu yeni surumle yeniden baslatacak" -f $target)
exit 0
