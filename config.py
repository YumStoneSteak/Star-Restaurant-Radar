from __future__ import annotations

import json
import logging
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

APP_NAME = "StarRestaurantRadar"
APP_TITLE = "StarRestaurantRadar"
APP_TOAST_APP_ID = "StarRestaurantRadar"
APP_PRODUCT_NAME = "StarRestaurantRadar"
APP_VERSION = "1.2.0"
GITHUB_REPO = "YumStoneSteak/Star-Restaurant-Radar"
DEFAULT_NOTIFICATION_TIME = "09:30"
LEGACY_APP_NAMES = ("ByeolsikdangNotifier",)
if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).resolve().parent
    if exe_dir.parent.name.lower() == "dist":
        BASE_DIR = exe_dir.parent.parent
    elif exe_dir.name.lower() == "dist":
        BASE_DIR = exe_dir.parent
    else:
        BASE_DIR = exe_dir
else:
    BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"


@dataclass
class AppConfig:
    instagram_username: str = "byeolsikdang"
    notification_time: str = DEFAULT_NOTIFICATION_TIME
    enabled_weekdays: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    exclude_korean_holidays: bool = True
    only_today_posts: bool = True
    prevent_duplicate: bool = True
    fallback_link_only_notification: bool = True
    notification_mode: str = "windows_toast"
    open_detail_on_click: bool = True
    cache_dir: str = "cache"
    log_dir: str = "logs"
    client_mode: str = "auto"
    mock_on_web_failure: bool = False
    use_instagram_login_session: bool = True
    instagram_session_dir: str = "instagram_session"
    test_post_url: str = ""
    test_image_url: str = ""
    holiday_failure_mode: str = "continue"
    start_on_boot: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        defaults = asdict(cls())
        cleaned = {key: data.get(key, value) for key, value in defaults.items()}
        cleaned["instagram_username"] = str(cleaned["instagram_username"]).strip().lstrip("@") or "byeolsikdang"
        cleaned["notification_time"] = normalize_time(str(cleaned["notification_time"]))
        cleaned["enabled_weekdays"] = normalize_weekdays(cleaned["enabled_weekdays"])
        cleaned["only_today_posts"] = True
        cleaned["notification_mode"] = "windows_toast"
        cleaned["client_mode"] = str(cleaned["client_mode"] or "auto").lower()
        if cleaned["client_mode"] not in {"auto", "web", "mock"}:
            cleaned["client_mode"] = "auto"
        if cleaned["holiday_failure_mode"] not in {"continue", "stop"}:
            cleaned["holiday_failure_mode"] = "continue"
        return cls(**cleaned)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def cache_path(self) -> Path:
        return resolve_app_path(self.cache_dir)

    @property
    def log_path(self) -> Path:
        return resolve_app_path(self.log_dir)

    @property
    def instagram_session_path(self) -> Path:
        return resolve_app_path(self.instagram_session_dir)


def resolve_app_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def normalize_time(value: str) -> str:
    parts = value.strip().split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError, IndexError):
        return DEFAULT_NOTIFICATION_TIME
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return DEFAULT_NOTIFICATION_TIME
    return f"{hour:02d}:{minute:02d}"


def normalize_weekdays(value: Any) -> list[int]:
    if not isinstance(value, list):
        return [1, 2, 3, 4, 5]
    days = sorted({int(day) for day in value if str(day).isdigit() and 1 <= int(day) <= 7})
    return days or [1, 2, 3, 4, 5]


def backup_corrupt_file(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".broken-{stamp}.bak")
    shutil.move(str(path), str(backup_path))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        config = AppConfig()
        save_config(config, path)
        return config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        backup_corrupt_file(path)
        config = AppConfig()
        save_config(config, path)
        return config
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    write_json(path, config.to_dict())
    ensure_runtime_dirs(config)


def ensure_runtime_dirs(config: AppConfig) -> None:
    config.cache_path.mkdir(parents=True, exist_ok=True)
    config.log_path.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "assets").mkdir(parents=True, exist_ok=True)


def setup_logging(config: AppConfig, quiet: bool = False) -> None:
    ensure_runtime_dirs(config)
    log_file = config.log_path / f"{datetime.now():%Y-%m-%d}.log"
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    if not quiet:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
