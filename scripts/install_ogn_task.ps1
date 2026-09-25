# Register (or refresh) the Windows scheduled task that saves the club ships' OGN tracks.
# Runs collector/ogn_tracks.py three times a day. If the laptop was off or asleep at a run time,
# Task Scheduler runs it as soon as the laptop is back ("StartWhenAvailable"), which keeps us inside
# FlightBook's 24 hour window as long as the laptop is opened once a day.
#   powershell -ExecutionPolicy Bypass -File scripts\install_ogn_task.ps1
#   Unregister-ScheduledTask -TaskName "chase-lift OGN tracks" -Confirm:$false     # to remove it
$ErrorActionPreference = "Stop"
$name = "chase-lift OGN tracks"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$script = Join-Path $repo "collector\ogn_tracks.py"
$python = (Get-Command python).Source
$pythonw = Join-Path (Split-Path $python -Parent) "pythonw.exe"   # no console window; the script logs to a file
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $repo
$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At 07:30),
    (New-ScheduledTaskTrigger -Daily -At 13:00),
    (New-ScheduledTaskTrigger -Daily -At 21:00)
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew -Compatibility Win8
Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Settings $settings -Force `
    -Description "Saves OGN FlightBook IGC tracks of GBSC's K1 and ASW 19 to ~\chase-lift-data\igc (collector/ogn_tracks.py). Log: ~\chase-lift-data\ogn_tracks.log" | Out-Null
Get-ScheduledTask -TaskName $name | Select-Object TaskName, State
Write-Host "Next runs:"; (Get-ScheduledTaskInfo -TaskName $name).NextRunTime
