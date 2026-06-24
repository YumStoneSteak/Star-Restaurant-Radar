param(
  [string]$Version = "1.1.0",
  [string]$MakensisPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Find-Makensis {
  param([string]$PreferredPath)

  if ($PreferredPath -and (Test-Path $PreferredPath)) {
    return (Resolve-Path $PreferredPath).Path
  }

  $Command = Get-Command makensis -ErrorAction SilentlyContinue
  if ($Command) {
    return $Command.Source
  }

  $Candidates = @(
    "C:\Program Files\NSIS\makensis.exe",
    "C:\Program Files (x86)\NSIS\makensis.exe",
    (Join-Path $Root "tools\nsis\makensis.exe"),
    (Join-Path $Root "tools\nsis-3.12\makensis.exe"),
    (Join-Path $Root "tools\nsis-3.12\Bin\makensis.exe")
  )
  foreach ($Candidate in $Candidates) {
    if (Test-Path $Candidate) {
      return $Candidate
    }
  }

  throw "makensis.exe를 찾지 못했습니다. NSIS를 설치하거나 -MakensisPath로 makensis.exe 경로를 지정해 주세요."
}

$Makensis = Find-Makensis -PreferredPath $MakensisPath

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "build.ps1")
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller build failed. exit=$LASTEXITCODE"
}

$InstallerPath = Join-Path $Root "dist\StarRestaurantRadar-Setup-v$Version.exe"
if (Test-Path $InstallerPath) {
  Remove-Item -LiteralPath $InstallerPath -Force
}

& $Makensis "/INPUTCHARSET" "UTF8" (Join-Path $Root "installer\StarRestaurantRadar.nsi")
if ($LASTEXITCODE -ne 0) {
  throw "NSIS 설치 파일 빌드에 실패했습니다. exit=$LASTEXITCODE"
}

if (-not (Test-Path $InstallerPath)) {
  throw "설치 파일이 생성되지 않았습니다: $InstallerPath"
}

$Hash = Get-FileHash -Path $InstallerPath -Algorithm SHA256
$ChecksumPath = "$InstallerPath.sha256"
"$($Hash.Hash.ToLower())  $(Split-Path -Leaf $InstallerPath)" | Set-Content -Path $ChecksumPath -Encoding ASCII

Write-Host "NSIS 설치 파일 빌드 완료: $InstallerPath"
Write-Host "SHA256 파일 생성 완료: $ChecksumPath"
