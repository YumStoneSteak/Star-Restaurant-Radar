# StarRestaurantRadar

StarRestaurantRadar는 별식당 Instagram 계정 `@byeolsikdang`의 최신 게시물을 정해진 시간에 확인하고, 메뉴 이미지를 Windows 알림으로 보여주는 데스크톱 앱입니다.

## 설치 방법

1. GitHub Releases에서 `StarRestaurantRadar-Setup-v1.2.0.exe`를 다운로드합니다.
2. 다운로드한 설치 파일을 실행합니다.
3. 설치가 끝나면 설정 화면이 한 번 자동으로 열립니다.
4. 기본 알림 시간은 평일 오전 9시 30분입니다. 원하는 시간으로 바꾼 뒤 창을 닫으면 됩니다.

설정 화면에서 아무것도 누르지 않고 닫아도 앱은 자동 실행과 예약 알림을 적용합니다.

- 기본 설치 위치: `%LOCALAPPDATA%\Programs\StarRestaurantRadar`
- 실행 파일: `StarRestaurantRadar.exe`
- 작업 스케줄러 이름: `StarRestaurantRadar`
- 기존 설정, 캐시, 로그, Instagram 로그인 세션은 업데이트 설치 중 보존됩니다.

## 사용 방법

설정 화면에서는 알림 시간과 컴퓨터 부팅 시 자동 실행만 조정합니다. 별도의 저장 버튼은 없습니다. 알림 시간을 바꾸면 바로 저장되고 다음 예약 알림에 적용됩니다.

알림 시간은 위·아래 화살표 없이 숫자를 직접 선택하거나 입력합니다. 바로 실행 동작은 2×2 버튼 배열에서 사용할 수 있습니다.

설정 화면을 닫아도 앱은 종료되지 않고 Windows 트레이에 남아 계속 동작합니다. 예약 시간이 됐을 때 트레이 앱이 실행 중이 아니면 앱을 먼저 트레이로 실행한 뒤 게시물 확인을 진행합니다.

트레이 아이콘을 우클릭하면 다음 메뉴를 사용할 수 있습니다.

- `설정창 열기`
- `최신 메뉴 확인`
- `Instagram 로그인 세션 만들기`
- `업데이트 확인`
- `종료`

## Instagram 로그인 세션

Instagram이 공개 조회를 막는 경우가 있어 실제 로그인이 필요할 수 있습니다. 이때 `Instagram 로그인 세션 만들기`를 누릅니다.

앱은 먼저 Chrome을 찾고, Chrome이 없으면 Microsoft Edge로 Instagram 로그인 창을 엽니다. Chrome과 Edge가 모두 없으면 설치가 필요하다는 안내를 보여줍니다.

브라우저 창이 열리면 실제 Instagram 계정으로 로그인해야 합니다. 평소 Chrome에 로그인되어 있어도 StarRestaurantRadar 전용 브라우저 세션에는 자동으로 공유되지 않습니다. 로그인 후 `@byeolsikdang` 프로필이나 게시물 목록이 보이면 브라우저 창을 닫으면 됩니다.

로그인 세션은 앱 폴더의 `instagram_session` 폴더에 저장됩니다.

## 업데이트

트레이 메뉴 또는 설정 화면에서 `업데이트 확인`을 누르면 GitHub Releases의 최신 버전을 확인합니다.

현재 설치된 버전보다 새 버전이 있으면 설치 파일을 다운로드하고, `.sha256` 파일이 함께 있으면 무결성 검사를 한 뒤 자동으로 업데이트 설치를 시작합니다. 업데이트 확인은 사용자가 직접 눌렀을 때만 실행됩니다.

## 자주 묻는 문제

### 알림은 왔는데 트레이 아이콘이 안 보입니다

v1.1.0부터 예약 실행 시 트레이 앱이 없으면 먼저 트레이 앱을 실행하도록 정리했습니다. Windows가 트레이 아이콘을 숨긴 경우에는 작업 표시줄의 숨겨진 아이콘 영역을 확인해 주세요.

### 업데이트 확인에서 인증서 오류가 납니다

v1.1.0 설치 파일에는 GitHub HTTPS 검증에 필요한 인증서 묶음이 포함되어 있습니다. 그래도 오류가 계속되면 Windows 날짜/시간이 맞는지, 보안 프로그램이 HTTPS 검사를 가로채고 있는지 확인해 주세요.

### 게시물 조회가 막혀 링크 확인 알림이 나옵니다

Instagram이 비로그인 조회를 막은 상태일 수 있습니다. `Instagram 로그인 세션 만들기`를 눌러 실제 Instagram 로그인을 완료한 뒤 다시 확인해 주세요.

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
- `dist\StarRestaurantRadar-Setup-v1.2.0.exe` (설치 파일)
- `dist\StarRestaurantRadar-Setup-v1.2.0.exe.sha256`

## 검증

```powershell
..\v\Scripts\python.exe -m compileall -q .
..\v\Scripts\python.exe -m unittest discover -s tests
```

UI 스모크 테스트:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_SCALE_FACTOR='1'
.\dist\StarRestaurantRadar\StarRestaurantRadar.exe --ui-layout-smoke-test
$env:QT_SCALE_FACTOR='1.25'
.\dist\StarRestaurantRadar\StarRestaurantRadar.exe --ui-layout-smoke-test
$env:QT_SCALE_FACTOR='1.5'
.\dist\StarRestaurantRadar\StarRestaurantRadar.exe --ui-layout-smoke-test
.\dist\StarRestaurantRadar\StarRestaurantRadar.exe --tray-smoke-test
```
