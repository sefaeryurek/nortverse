# Nortverse - Backend denetleyicisi (Sprint 94 D2; eski start-backend.bat'in yerine).
# Gorev Zamanlayici "Backend" gorevi bunu PENCERE ACMADAN calistirir (backend-supervisor.bat uzerinden).
#
# Eski sarmalayicinin sorunlari (28 Ekim denetimi):
# - "timeout /t 30" gizli konsolda hic beklemiyordu (0,06 sn)
# - uyku aninda calisma suresi negatif cikiyor, cokme sayaci hic sifirlanmiyordu
# - port 8000 doluysa sessizce cikiyordu (yeniden deneme yok)
# Bu denetleyici:
# - tek kopya calisir (Local\NortverseBackend mutex) - tetikleyiciler sik olabilir: oturum acilisi, uyanma,
#   kilit acma ve 15 dakikada bir guvenlik agi
# - port 8000 bizim sunucumuzdaysa (app.cli.main serve) onu izler; yabanci bir surecse uyarir ve 60 sn'de bir
#   tekrar dener - asla sessizce cikmaz
# - her dakika scripts\logs\backend.heartbeat dosyasina durum yazar (saglik kontrolu bunu okur)
# - 10 dakikadan uzun calistiysa cokme sayaci sifirlanir; 5 cokmede uyari verir, 10 dk bekleyip devam eder

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "scripts\logs"
$log = Join-Path $logs "backend.log"
$startsLog = Join-Path $logs "backend_starts.log"
$heartbeat = Join-Path $logs "backend.heartbeat"
$env:PYTHONIOENCODING = "utf-8"
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Force $logs | Out-Null }

function Note([string]$message) {
    Add-Content -Path $startsLog -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message) -Encoding UTF8
}

$script:lastNotify = @{}
function Notify([string]$message, [string]$key) {
    # Ayni uyari 2 saatte bir kezden fazla gosterilmez
    $now = Get-Date
    if ($script:lastNotify.ContainsKey($key) -and ($now - $script:lastNotify[$key]).TotalHours -lt 2) { return }
    $script:lastNotify[$key] = $now
    & cmd.exe /c ('"{0}" "{1}"' -f (Join-Path $root "scripts\notify-error.bat"), $message) | Out-Null
}

function Write-Heartbeat([string]$state) {
    Set-Content -Path $heartbeat -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"), $state) -Encoding ASCII
}

function Get-PortOwner {
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $conn) { return $null }
    return Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $conn.OwningProcess)
}

function Test-Ours($process) {
    return ($null -ne $process) -and ($process.CommandLine -match "app\.cli\.main\s+serve")
}

function Test-Healthy {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 10
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Wait-Docker {
    while ($true) {
        & cmd.exe /c ('"{0}" "{1}"' -f (Join-Path $root "scripts\ensure-docker.bat"), $log) | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
        Note "Docker/PostgreSQL hazir degil, 60 sn sonra tekrar"
        Notify "Backend baslatilamadi - Docker/PostgreSQL hazir degil" "docker"
        Write-Heartbeat "docker-bekleniyor"
        Start-Sleep -Seconds 60
    }
}

function Rotate-Log {
    if ((Test-Path $log) -and (Get-Item $log).Length -gt 20MB) {
        Move-Item -Force $log (Join-Path $logs "backend.old.log") -ErrorAction SilentlyContinue
    }
}

$mutex = New-Object System.Threading.Mutex($false, "Local\NortverseBackend")
if (-not $mutex.WaitOne(0)) { exit 0 }  # zaten bir denetleyici calisiyor (sik tetikleyiciler normal)

Note "Denetleyici basladi"
Wait-Docker
$crashes = 0

while ($true) {
    $owner = Get-PortOwner
    if ($null -ne $owner) {
        if (Test-Ours $owner) {
            # Baska bir yoldan (elle / eski sarmalayici) acilmis bizim sunucumuz: kapanana kadar izle
            $ownerPid = $owner.ProcessId
            Note ("Port 8000'de calisan sunucu izleniyor (PID {0})" -f $ownerPid)
            while ($true) {
                $current = Get-PortOwner
                if ($null -eq $current -or $current.ProcessId -ne $ownerPid) { break }
                Write-Heartbeat ($(if (Test-Healthy) { "ok" } else { "yanit-yok" }) + " pid=$ownerPid izleniyor")
                Start-Sleep -Seconds 60
            }
            continue
        }
        Note ("Port 8000 yabanci bir surecte: PID {0} {1}" -f $owner.ProcessId, $owner.Name)
        Notify ("Backend baslatilamadi - port 8000 baska bir programda: {0}" -f $owner.Name) "port"
        Write-Heartbeat "port-yabanci"
        Start-Sleep -Seconds 60
        continue
    }

    Rotate-Log
    Add-Content -Path $log -Value ("[{0}] Backend basliyor" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Encoding UTF8
    $started = Get-Date
    $proc = Start-Process -FilePath "cmd.exe" -WindowStyle Hidden -PassThru `
        -WorkingDirectory (Join-Path $root "backend") `
        -ArgumentList ('/c python -m app.cli.main serve >> "{0}" 2>&1' -f $log)
    while (-not $proc.HasExited) {
        Write-Heartbeat ($(if (Test-Healthy) { "ok" } else { "basliyor/yanit-yok" }) + " pid=$($proc.Id)")
        $null = $proc.WaitForExit(60000)
    }
    $uptime = [int]((Get-Date) - $started).TotalSeconds
    if ($uptime -ge 600) { $crashes = 0 }
    $crashes += 1
    Add-Content -Path $log -Value ("[{0}] Backend durdu - kod {1}, {2} sn calisti, deneme {3}" -f `
        (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $proc.ExitCode, $uptime, $crashes) -Encoding UTF8
    Write-Heartbeat "durdu"
    if ($crashes -ge 5) {
        Note "Backend 5 kez ust uste coktu, 10 dk beklenip yeniden denenecek"
        Notify "Backend 5 kez coktu - scripts\logs\backend.log dosyasina bakin; 10 dk sonra yeniden denenecek" "crash"
        Start-Sleep -Seconds 600
        $crashes = 0
    } else {
        Start-Sleep -Seconds 30
    }
    Wait-Docker
}
