from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from config import APP_NAME, BASE_DIR, LEGACY_APP_NAMES, AppConfig

COMMAND_TIMEOUT_SECONDS = 10


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        detail = f"명령이 {COMMAND_TIMEOUT_SECONDS}초 안에 끝나지 않아 중단했습니다."
        return subprocess.CompletedProcess(command, 124, stdout, f"{stderr}\n{detail}".strip())


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
        return sys.executable, "--run-once"

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    return str(executable), f'"{BASE_DIR / "app.py"}" --run-once'


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
    result = run_command(command)
    if result.returncode != 0:
        return result

    settings_command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            f"$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries; "
            f"Set-ScheduledTask -TaskName '{APP_NAME}' -Settings $settings | Out-Null"
        ),
    ]
    settings_result = run_command(settings_command)
    return settings_result if settings_result.returncode != 0 else result


def unregister_task() -> subprocess.CompletedProcess[str]:
    result = run_command(["schtasks", "/Delete", "/F", "/TN", APP_NAME])
    cleanup_legacy_tasks()
    return result


def cleanup_legacy_tasks() -> None:
    for legacy_name in LEGACY_APP_NAMES:
        if legacy_name != APP_NAME:
            run_command(["schtasks", "/Delete", "/F", "/TN", legacy_name])


def script_path(name: str) -> Path:
    return BASE_DIR / name
