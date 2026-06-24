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

$DistRoot = Join-Path $Root "dist"
$StaleDistItems = @(
  "ByeolsikdangNotifier",
  "ByeolsikdangNotifier.exe",
  "StarRestaurantRadar-Setup-v*.exe",
  "StarRestaurantRadar-Setup-v*.exe.sha256",
  "Star-Restaurant-Radar-Setup-v*.exe",
  "Star-Restaurant-Radar-Setup-v*.exe.sha256",
  "assets",
  "cache",
  "instagram_session",
  "logs",
  "config.json",
  "state.json",
  "ui_layout_smoke_test.log"
)
if (Test-Path $DistRoot) {
  foreach ($Item in $StaleDistItems) {
    Get-ChildItem -Path $DistRoot -Filter $Item -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
  }
}

& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  throw "Dependency install failed. exit=$LASTEXITCODE"
}

$CertifiArgs = @()
$CertifiInfo = & $Python -c @'
import importlib
for name in ('certifi', 'pip._vendor.certifi'):
    try:
        module = importlib.import_module(name)
        print(name)
        print(module.where())
        raise SystemExit(0)
    except Exception:
        pass
raise SystemExit(1)
'@
if ($LASTEXITCODE -eq 0 -and $CertifiInfo.Count -ge 2) {
  $CertifiModule = [string]$CertifiInfo[0]
  $CertifiPath = [string]$CertifiInfo[1]
  $CertifiDest = $CertifiModule -replace '\.', '/'
  $CertifiArgs = @("--hidden-import", $CertifiModule, "--add-data", "$CertifiPath;$CertifiDest")
}

$PyInstallerArgs = @(
  $Mode,
  "--noconfirm",
  "--windowed",
  "--name", $AppName,
  "--icon", "assets\app_icon.ico",
  "--add-data", "assets;assets"
) + $CertifiArgs + @("app.py")

& $Python -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller build failed. exit=$LASTEXITCODE"
}

$AppDistRoot = Join-Path $Root "dist\$AppName"
if (Test-Path $AppDistRoot) {
  Copy-Item -LiteralPath (Join-Path $Root "assets") -Destination $AppDistRoot -Recurse -Force
}

Write-Host "빌드가 완료되었습니다. dist 폴더를 확인해 주세요."
