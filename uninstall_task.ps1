param(
  [string]$TaskName = "StarRestaurantRadar"
)

$TaskNames = @($TaskName, "ByeolsikdangNotifier") | Select-Object -Unique
foreach ($Name in $TaskNames) {
  $Existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if ($Existing) {
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    Write-Host "$Name scheduled task removed."
  } else {
    Write-Host "$Name scheduled task was not found."
  }
}
