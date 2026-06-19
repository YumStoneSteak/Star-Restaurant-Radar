param(
  [switch]$OneFile
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$AppName = "StarRestaurantRadar"
$WorkspacePython = Join-Path (Split-Path -Parent $Root) "v\Scripts\python.exe"
$LocalPython = Join-Path $Root ".venv\Scripts\python.exe"

if (Test-Path $WorkspacePython) {
  $Python = $WorkspacePython
} elseif (Test-Path $LocalPython) {
  $Python = $LocalPython
} else {
  $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $Python) {
  throw "python 명령을 찾을 수 없습니다. README의 설치 방법으로 가상환경을 먼저 만들어 주세요."
}

$Mode = "--onedir"
if ($OneFile) {
  $Mode = "--onefile"
}

& $Python -m pip install -r requirements.txt
& $Python -m PyInstaller $Mode --noconfirm --windowed --name $AppName `
  --icon "assets\app_icon.ico" `
  --add-data "assets;assets" `
  app.py

$DistRoot = Join-Path $Root "dist\$AppName"
if (Test-Path $DistRoot) {
  Copy-Item -LiteralPath (Join-Path $Root "assets") -Destination $DistRoot -Recurse -Force
}

Write-Host "빌드가 완료되었습니다. dist 폴더를 확인해 주세요."
