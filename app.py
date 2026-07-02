from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import winreg
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from config import APP_NAME, APP_TITLE, APP_VERSION, BASE_DIR, LEGACY_APP_NAMES, AppConfig, load_config, save_config, setup_logging
from image_cache import ImageCacheService
from instagram_client import create_client, create_login_session as open_instagram_login_session
from main import run_once
from scheduler import register_task, unregister_task


def format_last_checked_at(value: object, now: datetime | None = None) -> str:
    if not value:
        return "-"

    text = str(value)
    try:
        checked_at = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return text

    current = now or datetime.now().astimezone()
    if checked_at.tzinfo is not None and current.tzinfo is not None:
        checked_at = checked_at.astimezone(current.tzinfo)

    period = "오전" if checked_at.hour < 12 else "오후"
    display_hour = checked_at.hour % 12 or 12
    display_time = f"{period} {display_hour}:{checked_at.minute:02d}"
    if checked_at.date() == current.date():
        return f"오늘 {display_time}"
    if checked_at.date() == (current - timedelta(days=1)).date():
        return f"어제 {display_time}"
    return f"{checked_at.year}년 {checked_at.month}월 {checked_at.day}일 {display_time}"
from state_store import StateStore
from toast_service import open_url
from update_service import UpdateError, check_for_update, download_update_installer, install_update


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="StarRestaurantRadar")
    parser.add_argument("--detail", help="Open detail window for a post id")
    parser.add_argument("--open-url", help="Open a URL in the default browser")
    parser.add_argument("--test-run", action="store_true", help="Run one forced mock notification")
    parser.add_argument("--run-once", action="store_true", help="Run one normal notification check and exit")
    parser.add_argument("--scheduled-check", action="store_true", help="Run a scheduled check with a visible tray app")
    parser.add_argument("--force-notify", action="store_true", help="Ignore date and duplicate guards when used with --run-once")
    parser.add_argument("--login-instagram", action="store_true", help="Create a local Instagram login session")
    parser.add_argument("--check-latest", action="store_true", help="Check the latest Instagram post and print the result")
    parser.add_argument("--minimized", action="store_true", help="Start in the system tray without showing settings")
    parser.add_argument("--first-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--tray-smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ui-layout-smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--detail-layout-smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--settings-responsiveness-smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--toast-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--toast-title", default="", help=argparse.SUPPRESS)
    parser.add_argument("--toast-body", default="", help=argparse.SUPPRESS)
    parser.add_argument("--toast-permalink", default="", help=argparse.SUPPRESS)
    parser.add_argument("--toast-image", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.open_url:
        open_url(args.open_url)
        return 0
    if args.detail:
        from detail_window import run_detail

        return run_detail(args.detail)
    if args.detail_layout_smoke_test:
        from detail_window import run_detail

        return run_detail("smoke-test", smoke_test=True)
    if args.toast_worker:
        from toast_worker import show_toast

        show_toast(args.toast_title, args.toast_body, args.toast_permalink, args.toast_image)
        return 0
    if args.run_once:
        return run_once(force_notify=args.force_notify)
    if args.test_run:
        return run_once(force_mock=True, force_notify=True)
    if args.scheduled_check:
        if not acquire_tray_instance():
            return run_once()
        return run_settings_app(start_minimized=True, scheduled_check=True)
    if args.login_instagram:
        from instagram_client import create_login_session

        create_login_session(load_config())
        return 0
    if args.check_latest:
        return check_latest_cli()
    if args.tray_smoke_test:
        return run_settings_app(start_minimized=True, smoke_test=True)
    if args.ui_layout_smoke_test:
        return run_settings_app(start_minimized=True, ui_layout_test=True)
    if args.settings_responsiveness_smoke_test:
        return run_settings_app(settings_responsiveness_test=True)
    if not acquire_tray_instance():
        return 0
    return run_settings_app(start_minimized=args.minimized, first_run=args.first_run)


_TRAY_MUTEX_HANDLE = None


def acquire_tray_instance() -> bool:
    if os.name != "nt":
        return True

    import ctypes

    global _TRAY_MUTEX_HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}Tray")
    if not handle:
        return True
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False
    _TRAY_MUTEX_HANDLE = handle
    return True


def check_latest_cli() -> int:
    config = load_config()
    setup_logging(config, quiet=True)
    try:
        post = create_client(config).get_latest_post(config.instagram_username)
    except Exception as exc:
        StateStore().update(last_result="최신 게시물 확인 실패", last_error=str(exc))
        print(f"최신 게시물 확인 실패: {exc}")
        print("Instagram 로그인이 필요하면 다음 명령을 먼저 실행하세요:")
        print(r"..\v\Scripts\python.exe app.py --login-instagram")
        return 2

    if not post:
        StateStore().update(last_result="최신 게시물 없음", last_error=None)
        print("최신 게시물을 찾지 못했습니다.")
        print("Instagram 로그인이 필요하면 다음 명령을 먼저 실행하세요:")
        print(r"..\v\Scripts\python.exe app.py --login-instagram")
        return 2

    StateStore().update(
        last_checked_at=None,
        last_permalink=post.permalink,
        last_result=f"최신 게시물 확인 완료: {post.media_type}",
        last_error=None,
    )
    print(f"최신 게시물 링크: {post.permalink}")
    print(f"게시 시각: {post.published_at.isoformat() if post.published_at else '확인 불가'}")
    print(f"조회 방식: {post.media_type}")
    return 0


def startup_command() -> str:
    command = app_command("--minimized")
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def set_start_on_boot(enabled: bool) -> None:
    run_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key_path, 0, winreg.KEY_SET_VALUE) as key:
        for legacy_name in LEGACY_APP_NAMES:
            try:
                winreg.DeleteValue(key, legacy_name)
            except FileNotFoundError:
                pass
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def run_settings_app(
    start_minimized: bool = False,
    first_run: bool = False,
    smoke_test: bool = False,
    ui_layout_test: bool = False,
    scheduled_check: bool = False,
    settings_responsiveness_test: bool = False,
) -> int:
    try:
        from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, QTime, Qt, Signal
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import (
            QAbstractSpinBox,
            QApplication,
            QCheckBox,
            QComboBox,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMessageBox,
            QMenu,
            QPushButton,
            QScrollArea,
            QSizePolicy,
            QSystemTrayIcon,
            QTimeEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6가 설치되어 있지 않습니다. requirements.txt를 설치한 뒤 다시 실행해 주세요.")
        return 1

    from ui_theme import apply_light_theme, brand_pixmap, load_app_icon

    class SchedulerWorkerSignals(QObject):
        finished = Signal(object)

    class SchedulerWorker(QRunnable):
        def __init__(self, config: AppConfig, registrar=register_task) -> None:  # type: ignore[no-untyped-def]
            super().__init__()
            self.config = config
            self.registrar = registrar
            self.signals = SchedulerWorkerSignals()

        def run(self) -> None:
            try:
                result = self.registrar(self.config)
            except Exception as exc:
                result = exc
            self.signals.finished.emit(result)

    class SettingsWindow(QWidget):
        def __init__(self, auto_apply: bool = True, scheduler_registrar=register_task) -> None:  # type: ignore[no-untyped-def]
            super().__init__()
            self.auto_apply = auto_apply
            self.pending_apply_message: str | None = None
            self.config = load_config()
            if first_run and not self.config.start_on_boot:
                self.config.start_on_boot = True
            setup_logging(self.config)
            self.state_store = StateStore()
            self.really_quit = False
            self.quit_requested = False
            self.settings_dirty = False
            self.scheduler_busy = False
            self.pending_scheduler_request: tuple[AppConfig, str, bool] | None = None
            self.active_scheduler_worker: SchedulerWorker | None = None
            self.scheduler_pool = QThreadPool(self)
            self.scheduler_pool.setMaxThreadCount(1)
            self.scheduler_registrar = scheduler_registrar
            self.setWindowTitle(APP_TITLE)
            self.setObjectName("AppRoot")
            self.setMinimumSize(520, 500)
            self.resize(580, 570)
            apply_light_theme(self)
            self.app_icon = load_app_icon()
            self.setWindowIcon(self.app_icon)

            outer = QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
            self.scroll_area = QScrollArea()
            self.scroll_area.setObjectName("ContentScroll")
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.content_widget = QWidget()
            self.content_widget.setObjectName("ScrollContent")
            root = QVBoxLayout(self.content_widget)
            root.setContentsMargins(22, 18, 22, 18)
            root.setSpacing(10)
            self.scroll_area.setWidget(self.content_widget)
            outer.addWidget(self.scroll_area)

            header = QFrame()
            header.setObjectName("HeaderFrame")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(2, 0, 2, 0)
            header_layout.setSpacing(12)
            brand_icon = QLabel()
            brand_icon.setObjectName("BrandIcon")
            brand_icon.setFixedSize(58, 58)
            brand_icon.setPixmap(brand_pixmap(56))
            brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(brand_icon)

            header_copy = QVBoxLayout()
            header_copy.setSpacing(2)
            title = QLabel("별식당 메뉴 알림")
            title.setObjectName("Title")
            subtitle = QLabel("오늘 메뉴가 올라오는 작은 설렘을 놓치지 않게 알려드려요.")
            subtitle.setObjectName("Subtitle")
            subtitle.setWordWrap(True)
            header_copy.addWidget(title)
            header_copy.addWidget(subtitle)
            header_layout.addLayout(header_copy, 1)

            version_badge = QLabel(f"v{APP_VERSION}")
            version_badge.setObjectName("VersionBadge")
            version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(version_badge, 0, Qt.AlignmentFlag.AlignTop)
            root.addWidget(header)

            settings_card = self._card(minimum_height=112)
            self.settings_card = settings_card
            self.settings_layout = QGridLayout(settings_card)
            settings_layout = self.settings_layout
            self._configure_pair_grid(settings_layout)

            settings_title = QLabel("알림 설정")
            settings_title.setObjectName("SectionTitle")
            settings_layout.addWidget(settings_title, 0, 0, 1, 4)

            self.target_label = QLabel("@byeolsikdang")
            self.target_label.setObjectName("TargetAccount")
            self.time_input = QTimeEdit()
            self._prepare_control(self.time_input)
            hour, minute = [int(part) for part in self.config.notification_time.split(":")]
            self.time_input.setTime(QTime(hour, minute))
            self.time_input.setDisplayFormat("HH:mm")
            self.time_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.start_on_boot = QCheckBox("컴퓨터를 켤 때 자동 실행")
            self.start_on_boot.setObjectName("AutoStartCheck")
            self.start_on_boot.setChecked(self.config.start_on_boot)
            self.apply_timer = QTimer(self)
            self.apply_timer.setSingleShot(True)
            self.apply_timer.timeout.connect(self.apply_settings)

            self._add_field_pair(settings_layout, 1, 0, "대상 계정", self.target_label)
            self._add_field_pair(settings_layout, 1, 2, "알림 시간", self.time_input)
            auto_label = QLabel("자동 실행")
            auto_label.setObjectName("FieldLabel")
            settings_layout.addWidget(auto_label, 2, 0)
            settings_layout.addWidget(self.start_on_boot, 2, 1, 1, 3)
            root.addWidget(settings_card)

            button_card = self._card(minimum_height=140)
            self.button_card = button_card
            self.button_layout = QVBoxLayout(button_card)
            button_layout = self.button_layout
            button_layout.setContentsMargins(16, 12, 16, 12)
            button_layout.setSpacing(6)

            actions_title = QLabel("바로 실행")
            actions_title.setObjectName("SectionTitle")
            button_layout.addWidget(actions_title)

            self.action_grid = QGridLayout()
            self.action_grid.setHorizontalSpacing(8)
            self.action_grid.setVerticalSpacing(8)

            check_button = QPushButton("최신 메뉴 확인")
            check_button.setObjectName("PrimaryButton")
            check_button.clicked.connect(self.check_latest_now)
            login_button = QPushButton("Instagram 로그인")
            login_button.clicked.connect(self.create_login_session)
            update_button = QPushButton("업데이트 확인")
            update_button.clicked.connect(self.check_updates)
            quit_button = QPushButton("종료")
            quit_button.setObjectName("QuietButton")
            quit_button.clicked.connect(self.quit_from_tray)

            self.action_grid.addWidget(check_button, 0, 0)
            self.action_grid.addWidget(login_button, 0, 1)
            self.action_grid.addWidget(update_button, 1, 0)
            self.action_grid.addWidget(quit_button, 1, 1)
            button_layout.addLayout(self.action_grid)
            self.action_buttons = [check_button, login_button, update_button, quit_button]
            root.addWidget(button_card)

            status_card = QFrame()
            status_card.setObjectName("StatusCard")
            status_card.setMinimumHeight(120)
            status_layout = QVBoxLayout(status_card)
            status_layout.setContentsMargins(15, 11, 15, 11)
            status_layout.setSpacing(3)
            status_title = QLabel("최근 상태")
            status_title.setObjectName("SectionTitle")
            status_layout.addWidget(status_title)
            self.status = QLabel()
            self.status.setObjectName("StatusBody")
            self.status.setMinimumHeight(72)
            self.status.setWordWrap(True)
            self.status.setTextFormat(Qt.TextFormat.PlainText)
            self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            status_layout.addWidget(self.status)
            root.addWidget(status_card)
            self.create_tray_icon()
            self.time_input.timeChanged.connect(lambda _time: self.queue_settings_apply("알림 시간이 적용되었습니다."))
            self.start_on_boot.toggled.connect(lambda _checked: self.queue_settings_apply("자동 실행 설정이 적용되었습니다."))
            self.refresh_status()
            if self.auto_apply:
                self.apply_settings(show_message=first_run)

        def _card(self, minimum_height: int | None = None) -> QFrame:
            frame = QFrame()
            frame.setObjectName("SurfaceCard")
            if minimum_height is not None:
                frame.setMinimumHeight(minimum_height)
            return frame

        def _configure_pair_grid(self, layout: QGridLayout) -> None:
            layout.setContentsMargins(16, 13, 16, 13)
            layout.setHorizontalSpacing(8)
            layout.setVerticalSpacing(6)
            layout.setColumnMinimumWidth(0, 68)
            layout.setColumnMinimumWidth(2, 64)
            layout.setColumnStretch(1, 1)
            layout.setColumnStretch(3, 1)

        def _prepare_control(self, widget):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            return widget

        def _add_field_pair(self, layout: QGridLayout, row: int, column: int, label: str, widget) -> None:
            field_label = QLabel(label)
            field_label.setObjectName("FieldLabel")
            field_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            field_label.setWordWrap(True)
            layout.addWidget(field_label, row, column)
            layout.addWidget(widget, row, column + 1)

        def collect_config(self) -> AppConfig:
            return AppConfig(
                instagram_username="byeolsikdang",
                notification_time=self.time_input.time().toString("HH:mm"),
                enabled_weekdays=[1, 2, 3, 4, 5],
                exclude_korean_holidays=True,
                only_today_posts=True,
                prevent_duplicate=True,
                fallback_link_only_notification=True,
                notification_mode="windows_toast",
                open_detail_on_click=True,
                cache_dir="cache",
                log_dir="logs",
                client_mode="auto",
                mock_on_web_failure=False,
                use_instagram_login_session=True,
                instagram_session_dir="instagram_session",
                test_post_url="",
                test_image_url="",
                holiday_failure_mode="continue",
                start_on_boot=self.start_on_boot.isChecked(),
            )

        def _save_settings(self) -> None:
            self.config = self.collect_config()
            save_config(self.config)
            set_start_on_boot(self.config.start_on_boot)

        def queue_settings_apply(self, message: str | None = None) -> None:
            self.pending_apply_message = message
            self.settings_dirty = True
            if not self.auto_apply:
                return
            self.apply_timer.start(350)

        def apply_settings(self, show_message: bool = True) -> None:
            self.apply_timer.stop()
            self._save_settings()
            self.settings_dirty = False
            message = self.pending_apply_message or "설정이 자동 적용되었습니다."
            self.pending_apply_message = None
            self._queue_scheduler_registration(self.config, message, show_message)

        def _queue_scheduler_registration(self, config: AppConfig, message: str, show_message: bool) -> None:
            request = (config, message, show_message)
            if self.scheduler_busy:
                self.pending_scheduler_request = request
                return
            self._start_scheduler_registration(request)

        def _start_scheduler_registration(self, request: tuple[AppConfig, str, bool]) -> None:
            config, _message, _show_message = request
            self.scheduler_busy = True
            worker = SchedulerWorker(config, self.scheduler_registrar)
            self.active_scheduler_worker = worker
            worker.signals.finished.connect(
                lambda result, completed_request=request: self._scheduler_registration_finished(
                    result,
                    completed_request,
                )
            )
            self.scheduler_pool.start(worker)

        def _scheduler_registration_finished(
            self,
            result: object,
            request: tuple[AppConfig, str, bool],
        ) -> None:
            _config, success_message, show_message = request
            self.scheduler_busy = False
            self.active_scheduler_worker = None
            if isinstance(result, Exception):
                message = f"설정은 저장했지만 알림 시간 적용 중 오류가 발생했습니다: {result}"
                show_message = True
            elif result.returncode == 0:
                message = success_message
            else:
                message = f"설정은 저장했지만 알림 시간 적용에 실패했습니다: {result.stderr or result.stdout}"
                show_message = True

            if show_message:
                self.refresh_status(message)
                self.notify_tray(message)
            else:
                self.refresh_status()

            pending_request = self.pending_scheduler_request
            self.pending_scheduler_request = None
            if pending_request is not None:
                self._start_scheduler_registration(pending_request)
                return

            if self.quit_requested:
                self._finish_quit()

        def _finish_quit(self) -> None:
            self.really_quit = True
            self.quit_requested = False
            self.tray_icon.hide()
            QApplication.instance().quit()

        def send_test_notification(self) -> None:
            self._save_settings()
            self.notify_tray("테스트 알림을 실행합니다.", timeout=1500)
            QApplication.processEvents()
            result = run_once(force_mock=True, force_notify=True)
            self.refresh_status(f"테스트 알림 실행 완료: exit {result}")
            self.notify_tray(f"테스트 알림 실행 완료: exit {result}")

        def check_latest_now(self) -> None:
            self._save_settings()
            self.refresh_status("최신 게시물 이미지를 확인하고 알림을 보내는 중입니다...")
            self.notify_tray("최신 게시물을 확인합니다.", timeout=1500)
            QApplication.processEvents()
            result = run_once(force_notify=True)
            self.refresh_status(f"최신 게시물 확인 완료: exit {result}")
            if result == 0:
                self.notify_tray("최신 게시물 확인을 완료했습니다.")
            else:
                self.notify_tray("최신 게시물 확인에 실패했습니다.")

        def open_last_detail(self) -> None:
            post_id = self.state_store.load().get("last_notified_post_id")
            command = app_command("--detail", post_id or "latest")
            os.spawnv(os.P_NOWAIT, command[0], command)
            self.notify_tray("마지막 알림 화면을 여는 중입니다.")

        def create_login_session(self) -> None:
            self._save_settings()
            self.refresh_status("Instagram 로그인 세션용 브라우저 창을 여는 중입니다...")
            QApplication.processEvents()
            try:
                open_instagram_login_session(self.config)
            except Exception as exc:
                self.state_store.update(last_error=str(exc), last_result="Instagram 로그인 세션 창 열기 실패")
                self.refresh_status(f"Instagram 로그인 세션 창 열기 실패: {exc}")
                self.notify_tray("Instagram 로그인 세션 창 열기에 실패했습니다.")
                return
            self.refresh_status(
                "Instagram 로그인 세션 창을 열었습니다. 실제로 로그인한 뒤 프로필이 보이면 브라우저 창을 닫아 주세요."
            )
            self.notify_tray("Instagram 로그인 세션 창을 열었습니다.")

        def check_updates(self) -> None:
            self._save_settings()
            self.refresh_status(f"GitHub 릴리즈에서 최신 버전을 확인하는 중입니다... 현재 버전: {APP_VERSION}")
            self.notify_tray("업데이트를 확인합니다.", timeout=1500)
            QApplication.processEvents()
            try:
                update = check_for_update()
                if not update:
                    message = f"현재 최신 버전입니다. ({APP_VERSION})"
                    self.refresh_status(message)
                    self.notify_tray(message)
                    return

                self.refresh_status(f"{update.tag_name} 업데이트를 다운로드하고 있습니다...")
                QApplication.processEvents()
                installer_path = download_update_installer(update)
                self.refresh_status(f"{update.tag_name} 설치 파일 검증 완료. 업데이트 설치를 시작합니다.")
                self.notify_tray("업데이트 설치를 시작합니다. 앱이 곧 종료됩니다.")
                QApplication.processEvents()
                install_update(installer_path)
                self.really_quit = True
                QApplication.instance().quit()
            except UpdateError as exc:
                message = f"업데이트 확인 실패: {exc}"
                self.state_store.update(last_error=str(exc), last_result="업데이트 확인 실패")
                self.refresh_status(message)
                self.notify_tray("업데이트 확인에 실패했습니다.")

        def install_task(self) -> None:
            self._save_settings()
            result = register_task(self.config)
            self.refresh_status(result.stdout or result.stderr or "작업 스케줄러 등록 명령을 실행했습니다.")
            self.notify_tray("작업 스케줄러 등록 명령을 실행했습니다.")

        def uninstall_task(self) -> None:
            result = unregister_task()
            self.refresh_status(result.stdout or result.stderr or "작업 스케줄러 해제 명령을 실행했습니다.")
            self.notify_tray("작업 스케줄러 해제 명령을 실행했습니다.")

        def open_logs(self) -> None:
            self.config.log_path.mkdir(parents=True, exist_ok=True)
            os.startfile(self.config.log_path)  # type: ignore[attr-defined]
            self.notify_tray("로그 폴더를 열었습니다.")

        def clear_cache(self) -> None:
            removed = ImageCacheService(self.config).clear_cache()
            self.refresh_status(f"캐시 파일 {removed}개를 삭제했습니다.")
            self.notify_tray(f"캐시 파일 {removed}개를 삭제했습니다.")

        def run_scheduled_check(self) -> None:
            self.refresh_status("예약된 알림 확인을 실행합니다.")
            QApplication.processEvents()
            result = run_once()
            self.refresh_status(f"예약된 알림 확인 완료: exit {result}")
            if result != 0:
                self.notify_tray("예약된 알림 확인에 실패했습니다.")

        def notify_tray(self, message: str, title: str = APP_TITLE, timeout: int = 2500) -> None:
            tray_icon = getattr(self, "tray_icon", None)
            if tray_icon and tray_icon.isVisible():
                tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, timeout)

        def add_tray_action(self, label: str, handler) -> QAction:
            action = QAction(label, self.tray_menu)
            action.triggered.connect(handler)
            self.tray_menu.addAction(action)
            self.tray_actions.append(action)
            return action

        def create_tray_icon(self) -> None:
            self.tray_icon = QSystemTrayIcon(self.app_icon, self)
            self.tray_icon.setToolTip(APP_TITLE)
            self.tray_menu = QMenu(self)
            self.tray_actions: list[QAction] = []
            self.add_tray_action("설정창 열기", self.show_settings_from_tray)
            self.add_tray_action("최신 메뉴 확인", self.check_latest_now)
            self.add_tray_action("Instagram 로그인 세션 만들기", self.create_login_session)
            self.add_tray_action("업데이트 확인", self.check_updates)
            self.tray_menu.addSeparator()
            self.add_tray_action("종료", self.quit_from_tray)
            self.tray_icon.setContextMenu(self.tray_menu)
            self.tray_icon.activated.connect(self.on_tray_activated)
            self.tray_icon.show()

        def show_settings_from_tray(self) -> None:
            self.show()
            self.raise_()
            self.activateWindow()

        def on_tray_activated(self, reason) -> None:  # type: ignore[no-untyped-def]
            if reason in {
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.DoubleClick,
            }:
                self.show_settings_from_tray()

        def quit_from_tray(self) -> None:
            self.quit_requested = True
            if self.settings_dirty or self.apply_timer.isActive():
                self.apply_settings(show_message=False)
            if self.scheduler_busy or self.pending_scheduler_request is not None:
                message = "설정 적용을 마무리한 뒤 종료합니다. 창은 계속 응답합니다."
                self.refresh_status(message)
                self.notify_tray(message)
                return
            self._finish_quit()

        def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            if self.auto_apply and (self.settings_dirty or self.apply_timer.isActive()):
                self.apply_settings(show_message=False)
            if self.really_quit or not QSystemTrayIcon.isSystemTrayAvailable():
                event.accept()
                return
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                APP_TITLE,
                "설정창은 닫혔지만 트레이에서 계속 실행 중입니다.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

        def refresh_status(self, message: str | None = None) -> None:
            state = self.state_store.load()
            lines = []
            if message:
                lines.append(message)
                lines.append("")
            lines.extend(
                [
                    f"최근 확인  {format_last_checked_at(state.get('last_checked_at'))}",
                    f"결과  {state.get('last_result') or '-'}",
                    f"오류  {state.get('last_error') or '-'}",
                ]
            )
            self.status.setText("\n".join(lines))

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationDisplayName(APP_TITLE)
    app.setWindowIcon(load_app_icon())
    app.setQuitOnLastWindowClosed(False)
    scheduler_registrar = register_task
    if settings_responsiveness_test:
        def slow_test_registrar(_config: AppConfig) -> subprocess.CompletedProcess[str]:
            time.sleep(0.8)
            return subprocess.CompletedProcess(["settings-responsiveness-smoke-test"], 0, "", "")

        scheduler_registrar = slow_test_registrar

    window = SettingsWindow(
        auto_apply=not (smoke_test or ui_layout_test or settings_responsiveness_test),
        scheduler_registrar=scheduler_registrar,
    )
    if scheduled_check and not QSystemTrayIcon.isSystemTrayAvailable():
        window.really_quit = True
        window.close()
        return run_once()
    if smoke_test:
        expected_actions = [
            "설정창 열기",
            "최신 메뉴 확인",
            "Instagram 로그인 세션 만들기",
            "업데이트 확인",
            "종료",
        ]
        actual_actions = [action.text() for action in window.tray_menu.actions() if not action.isSeparator()]
        missing_actions = [label for label in expected_actions if label not in actual_actions]
        if missing_actions:
            print(f"Tray smoke test failed: missing actions: {', '.join(missing_actions)}")
            return 1

        window.hide()
        show_action = next(action for action in window.tray_actions if action.text() == "설정창 열기")
        show_action.trigger()
        QApplication.processEvents()
        if not window.isVisible():
            print("Tray smoke test failed: settings action did not show the window")
            return 1

        window.really_quit = True
        window.close()
        print("Tray smoke test passed")
        return 0

    if ui_layout_test:
        failures = []
        smoke_log = BASE_DIR / "ui_layout_smoke_test.log"
        window.resize(580, 560)
        window.show()
        QApplication.processEvents()

        if window.settings_layout.columnCount() != 4:
            failures.append("settings grid is not compact paired layout")

        if window.settings_card.minimumHeight() < 105:
            failures.append("settings section minimum height is too small")
        if not 130 <= window.button_card.minimumHeight() <= 145:
            failures.append("button section is not compact")
        if window.settings_layout.verticalSpacing() < 6:
            failures.append("settings row spacing is too small")
        if window.button_layout.spacing() < 6:
            failures.append("button vertical gap is too small")
        if window.action_grid.rowCount() != 2 or window.action_grid.columnCount() != 2:
            failures.append("action buttons are not arranged in a 2x2 grid")
        expected_grid = [
            (window.action_buttons[0], 0, 0),
            (window.action_buttons[1], 0, 1),
            (window.action_buttons[2], 1, 0),
            (window.action_buttons[3], 1, 1),
        ]
        for expected_button, row, column in expected_grid:
            item = window.action_grid.itemAtPosition(row, column)
            if item is None or item.widget() is not expected_button:
                failures.append(f"action grid position is wrong: row={row} column={column}")
        if window.time_input.buttonSymbols() != QAbstractSpinBox.ButtonSymbols.NoButtons:
            failures.append("time input arrow buttons are still enabled")
        if window.start_on_boot.objectName() != "AutoStartCheck":
            failures.append("auto-start contrast style is missing")
        if window.action_buttons[0].objectName() != "PrimaryButton":
            failures.append("primary action style is missing")
        if window.action_buttons[-1].objectName() != "QuietButton":
            failures.append("quiet exit style is missing")
        if window.scroll_area.verticalScrollBar().maximum() != 0:
            failures.append("unexpected vertical scroll at 580x560")

        relevant_widgets = []
        for widget_class in [QLabel, QLineEdit, QTimeEdit, QComboBox, QCheckBox, QPushButton]:
            relevant_widgets.extend(window.content_widget.findChildren(widget_class))

        visible_widgets = [widget for widget in relevant_widgets if widget.isVisible()]
        for widget in visible_widgets:
            if widget.height() + 1 < widget.sizeHint().height():
                label = widget.text() if hasattr(widget, "text") else widget.__class__.__name__
                failures.append(f"widget is clipped: {label} height={widget.height()} hint={widget.sizeHint().height()}")

        rectangles = []
        for widget in visible_widgets:
            top_left = widget.mapTo(window.content_widget, widget.rect().topLeft())
            rectangles.append((widget, widget.rect().translated(top_left)))
        for index, (left_widget, left_rect) in enumerate(rectangles):
            for right_widget, right_rect in rectangles[index + 1 :]:
                if left_widget.parent() is right_widget or right_widget.parent() is left_widget:
                    continue
                if left_rect.adjusted(1, 1, -1, -1).intersects(right_rect.adjusted(1, 1, -1, -1)):
                    left_label = left_widget.text() if hasattr(left_widget, "text") else left_widget.__class__.__name__
                    right_label = right_widget.text() if hasattr(right_widget, "text") else right_widget.__class__.__name__
                    failures.append(f"widgets overlap: {left_label} / {right_label}")

        window.really_quit = True
        window.close()
        if failures:
            smoke_log.write_text(
                "UI layout smoke test failed:\n" + "\n".join(f"- {failure}" for failure in failures),
                encoding="utf-8",
            )
            print("UI layout smoke test failed:")
            for failure in failures:
                print(f"- {failure}")
            return 1
        smoke_log.write_text("UI layout smoke test passed", encoding="utf-8")
        print("UI layout smoke test passed")
        return 0

    if settings_responsiveness_test:
        result: dict[str, float | bool] = {"tick_delay": 99.0, "timed_out": False}
        started_at = time.perf_counter()

        def record_ui_tick() -> None:
            result["tick_delay"] = time.perf_counter() - started_at

        def fail_on_timeout() -> None:
            result["timed_out"] = True
            window.really_quit = True
            QApplication.instance().quit()

        QTimer.singleShot(50, record_ui_tick)
        QTimer.singleShot(3000, fail_on_timeout)
        window.apply_settings(show_message=False)
        window.quit_requested = True
        app.exec()
        tick_delay = float(result["tick_delay"])
        if bool(result["timed_out"]) or tick_delay >= 0.3:
            print(f"Settings responsiveness smoke test failed: tick_delay={tick_delay:.3f}")
            return 1
        print(f"Settings responsiveness smoke test passed: tick_delay={tick_delay:.3f}")
        return 0

    if scheduled_check:
        QTimer.singleShot(0, window.run_scheduled_check)

    if (start_minimized or scheduled_check) and QSystemTrayIcon.isSystemTrayAvailable():
        window.hide()
        window.tray_icon.showMessage(
            APP_TITLE,
            "StarRestaurantRadar is running in the tray.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )
    else:
        window.show()
    return app.exec()


def app_command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


if __name__ == "__main__":
    raise SystemExit(main())
