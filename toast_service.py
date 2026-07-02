from __future__ import annotations

import logging
import subprocess
import sys
import webbrowser
from pathlib import Path

from config import BASE_DIR, AppConfig
from image_cache import ImageCacheService
from instagram_client import InstagramPost

LOGGER = logging.getLogger(__name__)


class ToastService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def show_menu_notification(self, post: InstagramPost, image_path: Path | None) -> str:
        if post.media_type == "lookup_failure":
            title = "별식당 메뉴 확인 필요"
            body = "게시물 조회가 막혀 링크로 확인해 주세요."
        else:
            title = "오늘의 별식당 메뉴"
            body = "메뉴가 올라왔어요."

        if self.config.notification_mode != "windows_toast":
            return "지원하는 알림 방식이 아니어서 건너뜀"

        result = self._show_with_win11toast(title, body, image_path, post.permalink)
        if result:
            return result
        result = self._show_with_powershell(title, body)
        if result:
            return result
        return "알림 구성 요소가 없어 알림을 표시하지 못함"

    def open_latest_detail(self, post_id: str) -> None:
        subprocess.Popen([sys.executable, str(BASE_DIR / "app.py"), "--detail", post_id], close_fds=True)

    def _show_with_win11toast(
        self,
        title: str,
        body: str,
        image_path: Path | None,
        permalink: str,
    ) -> str | None:
        try:
            import win11toast  # noqa: F401
        except ImportError:
            return None

        if getattr(sys, "frozen", False):
            command = [
                sys.executable,
                "--toast-worker",
                "--toast-title",
                title,
                "--toast-body",
                body,
                "--toast-permalink",
                permalink,
            ]
        else:
            command = [
                sys.executable,
                str(BASE_DIR / "toast_worker.py"),
                "--title",
                title,
                "--body",
                body,
                "--permalink",
                permalink,
            ]
        toast_image_path = self._prepare_toast_image(image_path)
        if toast_image_path and toast_image_path.exists():
            if getattr(sys, "frozen", False):
                command.extend(["--toast-image", str(toast_image_path)])
            else:
                command.extend(["--image", str(toast_image_path)])

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(
                command,
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=creationflags,
            )
            return "알림 표시 요청 완료"
        except OSError:
            LOGGER.exception("Could not launch toast worker.")
            return None

    def _prepare_toast_image(self, image_path: Path | None) -> Path | None:
        if not image_path or not image_path.exists():
            return None
        return ImageCacheService(self.config).create_toast_image(image_path) or image_path

    def _show_with_powershell(self, title: str, body: str) -> str | None:
        script = (
            "Add-Type -AssemblyName PresentationFramework;"
            f"[System.Windows.MessageBox]::Show('{escape_ps(body)}','{escape_ps(title)}') | Out-Null"
        )
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                close_fds=True,
            )
            return "대체 알림창 표시 완료"
        except OSError:
            LOGGER.exception("PowerShell MessageBox fallback failed.")
            return None


def escape_ps(value: str) -> str:
    return value.replace("'", "''")


def open_url(url: str) -> None:
    if url:
        webbrowser.open(url)
