# Nortverse - Frontend denetleyicisi (Sprint 94 E6): uretim sunucusu (next start, 127.0.0.1:3000).
# Gorev Zamanlayici "Frontend" gorevi bunu PENCERE ACMADAN calistirir (frontend-supervisor.bat uzerinden);
# tetikleyiciler Backend ile ayni (oturum acilisi, uyanis, kilit acma, 15 dk), tek kopya calisir.
#
# - Gelistirme modu yerine uretim: hata ekrani kaynak/dosya yolu gostermez, __nextjs_source-map yok, hizli.
# - "-H 127.0.0.1" zorunlu: yoksa sunucu tum aga acilir. Disaridan erisim sadece Tailscale serve ile.
# - Hangi derleme: frontend\.prod-slot (a|b). Derleme yoksa once scripts\frontend-build.ps1 calisir.
#   frontend-build yeni bir yuvayi etkinlestirince sunucu en gec 15 sn icinde yeniden baslatilir.
# - Port 3000 baska bir surecteyse uyarir, 60 sn'de bir tekrar dener; bizim sunucumuzsa izler.
# - Her dakika scripts\logs\frontend.heartbeat; 10 dk'dan uzun calistiysa cokme sayaci sifirlanir.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$front = Join-Path $root "frontend"
$logs = Join-Path $root "scripts\logs"
$log = Join-Path $logs "frontend.log"
$startsLog = Join-Path $logs "frontend_starts.log"
$heartbeat = Join-Path $logs "frontend.heartbeat"
$slotFile = Join-Path $front ".prod-slot"
$port = 3000
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Force $logs | Out-Null }

function Note([string]$message) {
    Add-Content -Path $startsLog -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message) -Encoding UTF8
}

$script:lastNotify = @{}
function Notify([string]$message, [string]$key) {
    $now = Get-Date
    if ($script:lastNotify.ContainsKey($key) -and ($now - $script:lastNotify[$key]).TotalHours -lt 2) { return }
    $script:lastNotify[$key] = $now
    & cmd.exe /c ('"{0}" "{1}"' -f (Join-Path $root "scripts\notify-error.bat"), $message) | Out-Null
}

function Write-Heartbeat([string]$state) {
    Set-Content -Path $heartbeat -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"), $state) -Encoding ASCII
}

function Get-PortOwner {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $conn) { return $null }
    return Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $conn.OwningProcess)
}

function Test-Ours($process) {
    return ($null -ne $process) -and ($process.CommandLine -match 'next\\dist\\bin\\next"?\s+start')
}

function Test-Healthy {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/giris" -UseBasicParsing -TimeoutSec 10 -MaximumRedirection 0
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Get-Slot {
    if (Test-Path $slotFile) { return (Get-Content $slotFile -Raw).Trim() }
    return ""
}

function Ensure-Build {
    $slot = Get-Slot
    if ($slot -and (Test-Path (Join-Path $front ".next-prod-$slot\BUILD_ID"))) { return $slot }
    Note "Etkin derleme yok - frontend-build calistiriliyor"
    Write-Heartbeat "derleniyor"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\frontend-build.ps1") | Out-Null
    return Get-Slot
}

function Rotate-Log {
    if ((Test-Path $log) -and (Get-Item $log).Length -gt 20MB) {
        Move-Item -Force $log (Join-Path $logs "frontend.old.log") -ErrorAction SilentlyContinue
    }
}

$mutex = New-Object System.Threading.Mutex($false, "Local\NortverseFrontend")
if (-not $mutex.WaitOne(0)) { exit 0 }  # zaten bir denetleyici calisiyor

Note "Frontend denetleyicisi basladi"
$crashes = 0

while ($true) {
    $owner = Get-PortOwner
    if ($null -ne $owner) {
        if (Test-Ours $owner) {
            $ownerPid = $owner.ProcessId
            Note ("Port {0}'de calisan uretim sunucusu izleniyor (PID {1})" -f $port, $ownerPid)
            while ($true) {
                $current = Get-PortOwner
                if ($null -eq $current -or $current.ProcessId -ne $ownerPid) { break }
                Write-Heartbeat ($(if (Test-Healthy) { "ok" } else { "yanit-yok" }) + " pid=$ownerPid izleniyor")
                Start-Sleep -Seconds 60
            }
            continue
        }
        Note ("Port {0} baska bir surecte: PID {1} {2}" -f $port, $owner.ProcessId, $owner.CommandLine)
        Notify ("Frontend baslatilamadi - port {0} baska bir programda: {1}" -f $port, $owner.Name) "port"
        Write-Heartbeat "port-yabanci"
        Start-Sleep -Seconds 60
        continue
    }

    $slot = Ensure-Build
    if (-not $slot -or -not (Test-Path (Join-Path $front ".next-prod-$slot\BUILD_ID"))) {
        Note "Derleme basarisiz, 10 dk sonra tekrar denenecek"
        Notify "Frontend derlenemedi - scripts\logs\frontend-build.log; 10 dk sonra yeniden denenecek" "build"
        Write-Heartbeat "derleme-yok"
        Start-Sleep -Seconds 600
        continue
    }

    Rotate-Log
    Add-Content -Path $log -Value ("[{0}] Frontend basliyor (yuva {1})" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $slot) -Encoding UTF8
    $env:NEXT_DIST_DIR = ".next-prod-$slot"
    $env:NEXT_TELEMETRY_DISABLED = "1"
    $started = Get-Date
    $proc = Start-Process -FilePath "cmd.exe" -WindowStyle Hidden -PassThru -WorkingDirectory $front `
        -ArgumentList ('/c npx next start -H 127.0.0.1 -p {0} >> "{1}" 2>&1' -f $port, $log)
    $switched = $false
    while (-not $proc.HasExited) {
        Write-Heartbeat ($(if (Test-Healthy) { "ok" } else { "basliyor/yanit-yok" }) + " pid=$($proc.Id) yuva=$slot")
        $null = $proc.WaitForExit(15000)
        if (-not $proc.HasExited -and (Get-Slot) -ne $slot) {
            Note ("Yeni derleme etkin (yuva {0}) - sunucu yeniden baslatiliyor" -f (Get-Slot))
            & taskkill.exe /PID $proc.Id /T /F | Out-Null
            $switched = $true
        }
    }
    $uptime = [int]((Get-Date) - $started).TotalSeconds
    if ($switched) { continue }
    if ($uptime -ge 600) { $crashes = 0 }
    $crashes += 1
    Add-Content -Path $log -Value ("[{0}] Frontend durdu - kod {1}, {2} sn calisti, deneme {3}" -f `
        (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $proc.ExitCode, $uptime, $crashes) -Encoding UTF8
    Write-Heartbeat "durdu"
    if ($crashes -ge 5) {
        Note "Frontend 5 kez ust uste coktu, 10 dk beklenip yeniden denenecek"
        Notify "Frontend 5 kez coktu - scripts\logs\frontend.log dosyasina bakin; 10 dk sonra yeniden denenecek" "crash"
        Start-Sleep -Seconds 600
        $crashes = 0
    } else {
        Start-Sleep -Seconds 30
    }
}
