# Nortverse - Gorev Zamanlayici gorevlerini (yeniden) kurar.
# Calistirma (YONETICI PowerShell): powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install-tasks.ps1
#
# - Gorevler PENCERE ACMADAN calisir (run-hidden.vbs) -> yanlislikla kapatilip yarida kalmaz.
# - PC planlanan saatte kapaliysa, acilinca kacirilan calisma hemen yapilir (StartWhenAvailable).
# - Ayni gorev zaten calisiyorsa ikincisi baslamaz (IgnoreNew).
# - BackupDB ve RunPipeline uykudaki bilgisayari uyandirir (WakeToRun); ag yoksa zamanlanmis isler baslamaz.
# - Backend denetleyicisi oturum acilisinda, uyanista, kilit acilisinda ve 15 dk'da bir tetiklenir; tek kopya calisir.
# - Frontend denetleyicisi (uretim sunucusu, 127.0.0.1:3000) ayni tetikleyicilerle (Sprint 94 E6).
#
# Sprint 94 D1: UpdateScores2 (00:30) UpdateScores1'e birlestirildi - uyaninca ikisi paralel calisiyordu;
# pipeline sure siniri 2 -> 4 saat (72/87/70 dk surdu); gorev gecmisi acildi; aylik geri yukleme testi.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$vbs = Join-Path $root "scripts\run-hidden.vbs"
$path = "\Nortverse\"

function New-NortverseSettings([int]$hours, [switch]$wake) {
    $s = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RunOnlyIfNetworkAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours $hours) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    if ($wake) { $s.WakeToRun = $true }
    return $s
}

function New-NortverseTask([string]$name, [string]$bat, $triggers, [string]$description, $settings) {
    $action = New-ScheduledTaskAction -Execute "wscript.exe" `
        -Argument ('"{0}" "{1}"' -f $vbs, (Join-Path $root "scripts\$bat")) `
        -WorkingDirectory (Join-Path $root "scripts")
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $name -TaskPath $path -Action $action -Trigger $triggers `
        -Settings $settings -Principal $principal -Description $description -Force | Out-Null
    Write-Host "Kuruldu: $path$name"
}

# Gorev gecmisi (hangi gorev ne zaman calisti / neden calismadi) - varsayilan kapali
wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true

New-NortverseTask "BackupDB" "backup-db.bat" (New-ScheduledTaskTrigger -Daily -At "07:00") `
    "Gunluk PostgreSQL yedegi (C: son 7 gun, D: son 30 gun + .env)" (New-NortverseSettings 2 -wake)
New-NortverseTask "RunPipeline" "run-pipeline.bat" (New-ScheduledTaskTrigger -Daily -At "08:00") `
    "Gunluk bulten + analiz + DB, takip edilen ligler (hata olursa 10 dk sonra bir kez daha)" (New-NortverseSettings 4 -wake)
# Yarinin takip maclari bir gece once (mac oncesi karar uykuya bagli kalmasin) - 23:00 skor gorevinden sonra
New-NortverseTask "RunPipelineTomorrow" "run-pipeline-tomorrow.bat" (New-ScheduledTaskTrigger -Daily -At "23:20") `
    "Yarinin takip maclari aksamdan analiz edilir, mac oncesi kararlar erken dondurulur" (New-NortverseSettings 3)
# Haftada bir tum ligler (aday ligler icin veri birikir)
New-NortverseTask "RunPipelineAll" "run-pipeline-all.bat" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "09:30") `
    "Haftalik tum ligler pipeline'i" (New-NortverseSettings 4)

# Aksam saat basi skor guncellemesi (18:00-23:00) + gece 00:30 - tek gorev, iki kopya ayni anda calismaz
$scoreTriggers = @(18..23 | ForEach-Object { New-ScheduledTaskTrigger -Daily -At ("{0:00}:00" -f $_) })
$scoreTriggers += New-ScheduledTaskTrigger -Daily -At "00:30"
New-NortverseTask "UpdateScores1" "update-scores.bat" $scoreTriggers `
    "Skor guncelleme + tahmin defteri + kupon cozumu (18:00-23:00 saat basi ve 00:30)" (New-NortverseSettings 2)
if (Get-ScheduledTask -TaskPath $path -TaskName "UpdateScores2" -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskPath $path -TaskName "UpdateScores2" -Confirm:$false
    Write-Host "Kaldirildi: ${path}UpdateScores2 (UpdateScores1'e birlestirildi)"
}

# Aylik yedek geri yukleme testi (gecici konteyner 127.0.0.1:5544; canli DB'ye dokunmaz)
New-NortverseTask "RestoreTest" "restore-test.bat" (New-ScheduledTaskTrigger -Weekly -WeeksInterval 4 -DaysOfWeek Sunday -At "10:00") `
    "Yedegin gercekten geri yuklenebildigini 4 haftada bir dener" (New-NortverseSettings 2)

# Backend denetleyicisi: surekli calisir (sure siniri yok). Tetikleyiciler sik; denetleyici tek kopya calisir.
$backendSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$wakeClass = Get-CimClass -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler
$wake = New-CimInstance -CimClass $wakeClass -ClientOnly
$wake.Enabled = $true
$wake.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">' + `
    "*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]" + `
    '</Select></Query></QueryList>'
$unlockClass = Get-CimClass -ClassName MSFT_TaskSessionStateChangeTrigger -Namespace Root/Microsoft/Windows/TaskScheduler
$unlock = New-CimInstance -CimClass $unlockClass -ClientOnly
$unlock.Enabled = $true
$unlock.StateChange = 8   # oturum kilidi acildi
$unlock.UserId = $env:USERNAME
$safety = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 15)
New-NortverseTask "Backend" "backend-supervisor.bat" @($logon, $wake, $unlock, $safety) `
    "Backend denetleyicisi (oturum acilisi, uyanis, kilit acma, 15 dk; tek kopya; coksa yeniden baslatir)" $backendSettings
New-NortverseTask "Frontend" "frontend-supervisor.bat" @($logon, $wake, $unlock, $safety) `
    "Frontend uretim sunucusu denetleyicisi (127.0.0.1:3000; derleme yoksa derler; coksa yeniden baslatir)" $backendSettings

Get-ScheduledTask -TaskPath $path | Select-Object TaskName, State | Format-Table
