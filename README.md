# 스타 레스토랑 레이더

Star Restaurant Radar는 `@byeolsikdang` Instagram 계정의 최신 게시물 이미지를 설정한 시간에 확인하고 Windows 알림으로 보여주는 데스크톱 앱입니다.

## 설치

GitHub Releases에서 `Star-Restaurant-Radar-Setup-v1.0.0.exe`를 내려받아 실행합니다.

- 기본 설치 위치: `%LOCALAPPDATA%\Programs\Star Restaurant Radar`
- 앱 실행 파일: `StarRestaurantRadar.exe`
- 작업 스케줄러 이름: `StarRestaurantRadar`
- 기존 설정, 상태, 캐시, 로그, Instagram 로그인 세션은 업데이트 설치 중 보존됩니다.

## 사용

설정창에서는 알림 시간과 컴퓨터 부팅 시 자동 실행만 설정합니다. 저장하면 Windows 작업 스케줄러에 해당 시간이 자동 적용됩니다. 설정창을 닫아도 앱은 종료되지 않고 Windows 트레이 아이콘으로 남습니다.

트레이 메뉴에서 다음 기능을 사용할 수 있습니다.

- `설정창 열기`
- `최신 게시물 지금 확인`
- `Instagram 로그인 세션 만들기`
- `업데이트 확인`
- `종료`

## 업데이트

`업데이트 확인`을 누르면 GitHub Releases의 최신 버전을 확인합니다. 현재 설치 버전보다 새 버전이 있으면 NSIS 설치 파일을 다운로드하고 `.sha256` 파일이 있으면 검증한 뒤 silent install을 실행합니다. 업데이트 확인은 예약 실행하지 않고 사용자가 누를 때만 동작합니다.

## Instagram 로그인 세션

public 조회가 로그인 화면으로 막히면 `Instagram 로그인 세션 만들기`를 누릅니다. 전용 Chrome 창에서 Instagram에 로그인하고, `@byeolsikdang` 프로필 또는 게시물 그리드가 보이면 창을 닫습니다. 세션은 앱 폴더의 `instagram_session` 폴더에 저장됩니다.

## 개발 실행

Python 3.12 이상을 설치한 뒤 워크스페이스 루트에 짧은 이름의 가상환경을 만드는 방식을 권장합니다.

```powershell
cd "C:\Users\Office-PC\AppData\Local\Google\Chrome\User Data\Temp\code\Star-Restaurant"
python -m venv v
.\v\Scripts\python.exe -m pip install -r .\ByeolsikdangNotifier\requirements.txt
cd .\ByeolsikdangNotifier
..\v\Scripts\python.exe app.py
```

최신 게시물을 바로 확인하려면:

```powershell
..\v\Scripts\python.exe app.py --run-once --force-notify
```

로그인 세션 창을 열려면:

```powershell
..\v\Scripts\python.exe app.py --login-instagram
```

## 빌드

PyInstaller onedir 빌드:

```powershell
.\build.ps1
```

NSIS 설치 파일 빌드:

```powershell
.\build_installer.ps1
```

결과물:

- `dist\StarRestaurantRadar\StarRestaurantRadar.exe`
- `dist\Star-Restaurant-Radar-Setup-v1.0.0.exe`
- `dist\Star-Restaurant-Radar-Setup-v1.0.0.exe.sha256`

`build_installer.ps1`은 `makensis.exe`가 필요합니다. PATH 또는 `C:\Program Files\NSIS\makensis.exe`, `C:\Program Files (x86)\NSIS\makensis.exe`, `tools\nsis\makensis.exe`에서 찾고, 다른 위치에 있으면 `-MakensisPath`로 지정합니다.

## 검증

```powershell
..\v\Scripts\python.exe -m compileall -q -x "(\.venv|__pycache__|build|dist)" .
..\v\Scripts\python.exe -m unittest discover -s tests
```

UI 스모크 테스트:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_SCALE_FACTOR='1'
.\dist\StarRestaurantRadar\StarRestaurantRadar.exe --ui-layout-smoke-test
$env:QT_SCALE_FACTOR='1.25'
.\dist\StarRestaurantRadar\StarRestaurantRadar.exe --ui-layout-smoke-test
.\dist\StarRestaurantRadar\StarRestaurantRadar.exe --tray-smoke-test
```
