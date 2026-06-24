from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from config import APP_NAME, BASE_DIR, LEGACY_APP_NAMES, AppConfig


def task_days(config: AppConfig) -> str:
    mapping = {
        1: "MON",
        2: "TUE",
        3: "WED",
        4: "THU",
        5: "FRI",
        6: "SAT",
        7: "SUN",
    }
    return ",".join(mapping[day] for day in config.enabled_weekdays if day in mapping) or "MON,TUE,WED,THU,FRI"


def task_target() -> tuple[str, str]:
    if getattr(sys, "frozen", False):
        return sys.executable, "--scheduled-check"
    onefile = BASE_DIR / "dist" / f"{APP_NAME}.exe"
    if onefile.exists():
        return str(onefile), "--scheduled-check"
    packaged = BASE_DIR / "dist" / APP_NAME / f"{APP_NAME}.exe"
    if packaged.exists():
        return str(packaged), "--scheduled-check"
    return sys.executable, f'"{BASE_DIR / "app.py"}" --scheduled-check'


def register_task(config: AppConfig) -> subprocess.CompletedProcess[str]:
    cleanup_legacy_tasks()
    executable, arguments = task_target()
    command = [
        "schtasks",
        "/Create",
        "/F",
        "/TN",
        APP_NAME,
        "/SC",
        "WEEKLY",
        "/D",
        task_days(config),
        "/ST",
        config.notification_time,
        "/TR",
        f'"{executable}" {arguments}'.strip(),
    ]
    return subprocess.run(command, capture_output=True, text=True, cwd=BASE_DIR)


def unregister_task() -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["schtasks", "/Delete", "/F", "/TN", APP_NAME], capture_output=True, text=True, cwd=BASE_DIR)
    cleanup_legacy_tasks()
    return result


def cleanup_legacy_tasks() -> None:
    for legacy_name in LEGACY_APP_NAMES:
        if legacy_name != APP_NAME:
            subprocess.run(["schtasks", "/Delete", "/F", "/TN", legacy_name], capture_output=True, text=True, cwd=BASE_DIR)


def script_path(name: str) -> Path:
    return BASE_DIR / name
