# Nortverse - Gorev Zamanlayici gorevlerini (yeniden) kurar.
# Calistirma: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install-tasks.ps1
#
# - Gorevler PENCERE ACMADAN calisir (run-hidden.vbs) -> yanlislikla kapatilip yarida kalmaz.
# - PC planlanan saatte kapaliysa, acilinca kacirilan calisma hemen yapilir (StartWhenAvailable).
# - Ayni gorev zaten calisiyorsa ikincisi baslamaz; 2 saatte bitmezse durdurulur.
# - Backend gorevi oturum acilisinda baslar ve surekli calisir; hata olursa ekranda uyari (notify-error.bat).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$vbs = Join-Path $root "scripts\run-hidden.vbs"
$path = "\Nortverse\"

function New-NortverseTask([string]$name, [string]$bat, $triggers, [string]$description, $settings = $null) {
    $action = New-ScheduledTaskAction -Execute "wscript.exe" `
        -Argument ('"{0}" "{1}"' -f $vbs, (Join-Path $root "scripts\$bat")) `
        -WorkingDirectory (Join-Path $root "scripts")
    if ($null -eq $settings) {
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    }
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $name -TaskPath $path -Action $action -Trigger $triggers `
        -Settings $settings -Principal $principal -Description $description -Force | Out-Null
    Write-Host "Kuruldu: $path$name"
}

New-NortverseTask "BackupDB" "backup-db.bat" (New-ScheduledTaskTrigger -Daily -At "07:00") `
    "Gunluk PostgreSQL yedegi (son 7 gun)"
New-NortverseTask "RunPipeline" "run-pipeline.bat" (New-ScheduledTaskTrigger -Daily -At "08:00") `
    "Gunluk bulten + analiz + DB"

# Aksam saat basi skor guncellemesi (18:00-23:00) + gece 00:30
$evening = 18..23 | ForEach-Object { New-ScheduledTaskTrigger -Daily -At ("{0:00}:00" -f $_) }
New-NortverseTask "UpdateScores1" "update-scores.bat" $evening `
    "Skor guncelleme + tahmin defteri cozumu (18:00-23:00 saat basi)"
New-NortverseTask "UpdateScores2" "update-scores.bat" (New-ScheduledTaskTrigger -Daily -At "00:30") `
    "Skor guncelleme + tahmin defteri cozumu (gece gec biten maclar)"

# Backend: oturum acilinca baslar, surekli calisir (sure siniri yok); canli devre arasi kayitlari icin sart.
$backendSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
New-NortverseTask "Backend" "start-backend.bat" (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) `
    "Backend sunucusu (oturum acilisinda, coksa yeniden baslar)" $backendSettings

Get-ScheduledTask -TaskPath $path | Select-Object TaskName, State | Format-Table
