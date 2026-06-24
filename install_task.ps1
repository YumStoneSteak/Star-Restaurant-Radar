param(
  [string]$TaskName = "StarRestaurantRadar"
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $Root "config.json"
$NotifyTime = "10:00"

if (Test-Path $ConfigPath) {
  try {
    $Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
    if ($Config.notification_time) {
      $NotifyTime = [string]$Config.notification_time
    }
  } catch {
    Write-Host "Could not read config.json. Using default time 10:00."
  }
}

$OneFileExe = Join-Path $Root "dist\StarRestaurantRadar.exe"
$PackagedExe = Join-Path $Root "dist\StarRestaurantRadar\StarRestaurantRadar.exe"
$LegacyTaskName = "ByeolsikdangNotifier"
$WorkspaceVenvPython = Join-Path (Split-Path -Parent $Root) "v\Scripts\python.exe"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$AppPy = Join-Path $Root "app.py"

if (Test-Path $OneFileExe) {
  $Action = New-ScheduledTaskAction -Execute $OneFileExe -Argument "--scheduled-check" -WorkingDirectory (Split-Path -Parent $OneFileExe)
} elseif (Test-Path $PackagedExe) {
  $Action = New-ScheduledTaskAction -Execute $PackagedExe -Argument "--scheduled-check" -WorkingDirectory $Root
} elseif (Test-Path $WorkspaceVenvPython) {
  $Action = New-ScheduledTaskAction -Execute $WorkspaceVenvPython -Argument "`"$AppPy`" --scheduled-check" -WorkingDirectory $Root
} elseif (Test-Path $VenvPython) {
  $Action = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$AppPy`" --scheduled-check" -WorkingDirectory $Root
} else {
  $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
  if (-not $Python) {
    $Python = (Get-Command py -ErrorAction SilentlyContinue).Source
  }
  if (-not $Python) {
    throw "python or py command was not found. Install Python 3.12 or later."
  }
  $Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$AppPy`" --scheduled-check" -WorkingDirectory $Root
}

$At = [datetime]::ParseExact($NotifyTime, "HH:mm", $null)
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $At
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

if ($LegacyTaskName -ne $TaskName) {
  $LegacyTask = Get-ScheduledTask -TaskName $LegacyTaskName -ErrorAction SilentlyContinue
  if ($LegacyTask) {
    Unregister-ScheduledTask -TaskName $LegacyTaskName -Confirm:$false
  }
}

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "StarRestaurantRadar" -Force | Out-Null
Write-Host "$TaskName scheduled task registered for weekdays at $NotifyTime."
