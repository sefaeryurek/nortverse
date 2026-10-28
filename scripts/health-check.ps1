# Nortverse - Saglik kontrolu (Sprint 94 D4). "HealthCheck" gorevi 11:00-01:30 arasi 15 dk'da bir calistirir.
#
# Sorun bulursa notify-error.bat ile uyarir (ekran + masaustu notu + ayarliysa telefon/ntfy); ayni uyari 2 saatte
# bir kezden fazla gosterilmez. Her calismada healthchecks.io'ya ping atar (ayarliysa): bilgisayar uyur ya da
# kapanirsa ping kesilir ve healthchecks telefona haber verir - yerel hicbir betik bunu kendisi yapamaz.
# Ayarlar: scripts\alerts.local.env (ornek: alerts.example.env). Ayar yoksa dis servise hicbir sey gitmez.

param([switch]$DryRun)  # -DryRun: sonuclari ekrana yazar; uyari, durum dosyasi ve ping yok
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $root "scripts\logs"
$healthLog = Join-Path $logs "health.log"
$stateFile = Join-Path $logs "health-state.json"
$now = Get-Date
$results = New-Object System.Collections.Generic.List[object]

function Add-Check([string]$name, [bool]$ok, [string]$detail) {
    $results.Add([pscustomobject]@{ name = $name; ok = $ok; detail = $detail })
}

function Age-Minutes([string]$path) {
    if (-not (Test-Path $path)) { return $null }
    return [int]($now - (Get-Item $path).LastWriteTime).TotalMinutes
}

# 1. Veritabani konteyneri
$dbId = (& docker compose -f (Join-Path $root "docker-compose.yml") ps -q db 2>$null | Select-Object -First 1)
$dbHealth = if ($dbId) { (& docker inspect --format "{{.State.Health.Status}}" $dbId 2>$null) } else { "" }
Add-Check "veritabani" ($dbHealth -eq "healthy") ("konteyner: " + $(if ($dbHealth) { $dbHealth } else { "calismiyor" }))

# 2. Backend ve frontend: kalp atisi < 3 dk ve yanit
foreach ($svc in @(
        @{ name = "backend"; beat = "backend.heartbeat"; url = "http://127.0.0.1:8000/api/health" },
        @{ name = "frontend"; beat = "frontend.heartbeat"; url = "http://127.0.0.1:3000/giris" })) {
    $age = Age-Minutes (Join-Path $logs $svc.beat)
    $code = 0
    try { $code = (Invoke-WebRequest -Uri $svc.url -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 0).StatusCode } catch {}
    $ok = ($null -ne $age) -and ($age -lt 3) -and ($code -eq 200)
    Add-Check $svc.name $ok ("kalp atisi {0} dk once, yanit {1}" -f $(if ($null -ne $age) { $age } else { "yok" }), $code)
}

# 3. 13:00'ten sonra bugunun sabah pipeline'i basarili olmali
if ($now.Hour -ge 13 -or $now.Hour -lt 2) {
    $mark = Join-Path $logs "pipeline.ok"
    $day = if ($now.Hour -lt 2) { $now.Date.AddDays(-1) } else { $now.Date }
    $ok = (Test-Path $mark) -and ((Get-Item $mark).LastWriteTime -ge $day)
    Add-Check "pipeline" $ok $(if ($ok) { "bugun basarili" } else { "bugunun pipeline'i basarili bitmedi - scripts\logs\pipeline.log" })
}

# 4-8 (DB tarafi): canli IY dondurma, oran kaydi - backend CLI
Push-Location (Join-Path $root "backend")
$env:PYTHONIOENCODING = "utf-8"
$raw = & python -m app.cli.main health-report --json 2>$null | Select-Object -Last 1
Pop-Location
try {
    $report = $raw | ConvertFrom-Json
    foreach ($c in $report.checks) { Add-Check $c.name ([bool]$c.ok) $c.detail }
} catch {
    Add-Check "saglik_raporu" $false "health-report calismadi: $raw"
}

# 5. 19:00-01:00 arasi son basarili skor guncellemesi < 2 saat (18:00 calismasi 18:05'e kadar biter)
if ($now.Hour -ge 19 -or $now.Hour -lt 1) {
    $age = Age-Minutes (Join-Path $logs "scores.ok")
    $ok = ($null -ne $age) -and ($age -lt 120)
    Add-Check "skor_guncelleme" $ok ("son basarili skor guncellemesi: " + $(if ($null -ne $age) { "$age dk once" } else { "hic yok" }))
}

# 6. Yedekler: bugunun yedegi > 200 MB (09:00'dan sonra), D: kopyasi < 2 gun, bulut kopyasi < 8 gun (ayarliysa)
$cfg = @{}
$cfgFile = Join-Path $root "scripts\alerts.local.env"
if (Test-Path $cfgFile) {
    foreach ($line in Get-Content $cfgFile) {
        if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*)$') { $cfg[$Matches[1]] = $Matches[2].Trim() }
    }
}
if ($now.Hour -ge 9) {
    $today = Join-Path $root ("backups\nortverse_{0}.dump" -f $now.ToString("yyyy-MM-dd"))
    $size = if (Test-Path $today) { [int]((Get-Item $today).Length / 1MB) } else { 0 }
    Add-Check "yedek_bugun" ($size -gt 200) ("bugunun yedegi: {0} MB" -f $size)
}
$mirror = Get-ChildItem "D:\NortverseYedek\nortverse_*.dump" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
$mirrorAge = if ($mirror) { ($now - $mirror.LastWriteTime).TotalDays } else { 99 }
Add-Check "yedek_d" ($mirrorAge -lt 2) ("D: son kopya: " + $(if ($mirror) { "{0:N1} gun once" -f $mirrorAge } else { "yok" }))
if ($cfg["CLOUD_BACKUP_DIR"]) {
    $cloud = Get-ChildItem $cfg["CLOUD_BACKUP_DIR"] -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
    $cloudAge = if ($cloud) { ($now - $cloud.LastWriteTime).TotalDays } else { 99 }
    Add-Check "yedek_bulut" ($cloudAge -lt 8) ("bulut son kopya: " + $(if ($cloud) { "{0:N1} gun once" -f $cloudAge } else { "yok" }))
}

# 7. C: bos alan > 20 GB
$free = [int]((Get-PSDrive C).Free / 1GB)
Add-Check "disk_c" ($free -gt 20) ("C: bos alan {0} GB" -f $free)

# 8. Uzun islerin loglarinda "durduruldu" yok (son 30 satir)
foreach ($job in @("goal_events.log", "archive.log", "odds_ft.log", "odds_daily.log")) {
    $path = Join-Path $logs $job
    if (Test-Path $path) {
        $stopped = Get-Content $path -Tail 30 -Encoding UTF8 | Select-String -SimpleMatch "durduruldu" | Select-Object -Last 1
        Add-Check ("uzun_is_" + [IO.Path]::GetFileNameWithoutExtension($job)) ($null -eq $stopped) `
            $(if ($stopped) { "$job : is durduruldu - yeniden baslatin" } else { "calisiyor/bitti" })
    }
}

# Sonuc: log + uyari (2 saatte bir) + healthchecks ping
$failed = @($results | Where-Object { -not $_.ok })
$summary = if ($failed.Count) { ($failed | ForEach-Object { "{0}: {1}" -f $_.name, $_.detail }) -join " | " } else { "hepsi tamam" }
if ($DryRun) {
    $results | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
    exit $(if ($failed.Count) { 1 } else { 0 })
}
Add-Content -Path $healthLog -Value ("[{0}] {1}/{2} tamam - {3}" -f $now.ToString("yyyy-MM-dd HH:mm"), ($results.Count - $failed.Count), $results.Count, $summary) -Encoding UTF8

$state = @{}
if (Test-Path $stateFile) {
    try { (Get-Content $stateFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $state[$_.Name] = [datetime]$_.Value } } catch {}
}
$fresh = @($failed | Where-Object { -not $state.ContainsKey($_.name) -or ($now - $state[$_.name]).TotalHours -ge 2 })
if ($fresh.Count) {
    $message = "Saglik kontrolu: " + (($fresh | ForEach-Object { "{0} - {1}" -f $_.name, $_.detail }) -join "; ")
    $message = $message -replace '[()]', '' -replace '[&|<>^%"]', ' '  # notify-error.bat icin guvenli metin
    & cmd.exe /c ('"{0}" "{1}"' -f (Join-Path $root "scripts\notify-error.bat"), $message) | Out-Null
    foreach ($f in $fresh) { $state[$f.name] = $now }
}
foreach ($k in @($state.Keys)) { if (-not ($failed | Where-Object { $_.name -eq $k })) { $state.Remove($k) } }  # duzelen tekrar uyarabilsin
$state.GetEnumerator() | ForEach-Object -Begin { $o = @{} } -Process { $o[$_.Key] = $_.Value.ToString("o") } -End { $o } |
    ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8

& cmd.exe /c ('"{0}" nortverse-saglik {1}' -f (Join-Path $root "scripts\hc-ping.bat"), $(if ($failed.Count) { "fail" } else { "" })) | Out-Null
if ($failed.Count) { exit 1 } else { exit 0 }
