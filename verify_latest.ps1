$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path (Split-Path -Parent $Root) "v\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "가상환경 Python을 찾을 수 없습니다. README의 설치 방법을 먼저 실행해 주세요."
}

Set-Location $Root
& $Python app.py --check-latest

