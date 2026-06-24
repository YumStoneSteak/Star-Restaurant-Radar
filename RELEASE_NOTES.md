# StarRestaurantRadar v1.1.0

StarRestaurantRadar v1.1.0은 일반 사용자가 설치 후 바로 알림을 받을 수 있도록 첫 실행, 트레이 유지, Instagram 로그인 세션, Windows 토스트 알림, 업데이트 확인 흐름을 정리한 릴리즈입니다.

## 주요 변경 사항

- 프로그램 이름과 설치 파일 이름을 `StarRestaurantRadar`로 통일했습니다.
- 설치 직후 설정 화면이 한 번 자동으로 열립니다.
- 설정 화면을 그냥 닫아도 부팅 시 자동 실행과 예약 알림이 적용됩니다.
- `저장하고 알림 시간 적용` 버튼을 제거하고, 알림 시간을 바꾸면 바로 저장 및 적용되도록 했습니다.
- 예약 알림 실행 시 트레이 앱이 없으면 먼저 트레이 앱을 실행한 뒤 게시물 확인을 진행합니다.
- Windows 토스트 알림의 앱 표시 이름을 `StarRestaurantRadar`로 바꾸고, 이미지는 hero 배치와 110% 중앙 확대본을 사용해 글씨가 더 잘 보이게 했습니다.
- Chrome을 찾지 못하면 Microsoft Edge로 Instagram 로그인 세션 창을 열도록 했습니다.
- Instagram 로그인 세션 안내 문구를 실제 로그인이 필요하다는 점이 분명하게 보이도록 정리했습니다.
- GitHub 업데이트 확인에서 인증서 검증 실패가 나지 않도록 앱 패키지에 CA 인증서 묶음을 포함했습니다.
- 오래된 `ByeolsikdangNotifier` 이름의 실행/설치 흔적과 중복 bat 파일을 정리했습니다.

## 설치 파일

- `StarRestaurantRadar-Setup-v1.1.0.exe`
- `StarRestaurantRadar-Setup-v1.1.0.exe.sha256`

## 검증

- `..\v\Scripts\python.exe -m compileall -q .`
- `..\v\Scripts\python.exe -m unittest discover -s tests`
- 패키지된 `StarRestaurantRadar.exe --tray-smoke-test`
- 실제 GitHub Releases HTTPS 조회 확인
- NSIS 설치 파일 및 SHA256 파일 재생성

## 참고

Instagram이 공개 조회를 막는 경우에는 `Instagram 로그인 세션 만들기`를 눌러 브라우저 창에서 실제 Instagram 로그인을 완료해야 합니다. Chrome이 없으면 Edge를 사용하고, 둘 다 없으면 Chrome 또는 Edge 설치가 필요합니다.
