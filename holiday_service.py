from __future__ import annotations

import logging
from datetime import date

from config import AppConfig

LOGGER = logging.getLogger(__name__)


class HolidayService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def should_run(self, today: date) -> tuple[bool, str]:
        weekday = today.isoweekday()
        if weekday not in self.config.enabled_weekdays:
            return False, f"요일 제외: ISO weekday {weekday}"
        if self.config.exclude_korean_holidays and self.is_korean_holiday(today):
            return False, "한국 공휴일 제외"
        return True, "실행 대상 날짜"

    def is_korean_holiday(self, today: date) -> bool:
        try:
            import holidays  # type: ignore
        except ImportError:
            LOGGER.info("holidays package is not installed; Korean holiday check is skipped.")
            return False

        try:
            korea_holidays = holidays.country_holidays("KR", years=[today.year])
            return today in korea_holidays
        except Exception:
            LOGGER.exception("Korean holiday lookup failed.")
            if self.config.holiday_failure_mode == "stop":
                raise
            return False

