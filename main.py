from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path

from config import AppConfig, load_config, setup_logging
from holiday_service import HolidayService
from image_cache import ImageCacheService
from instagram_client import KST, InstagramPost, create_client, is_plausible_shortcode, parse_datetime
from state_store import StateStore, iso_now
from toast_service import ToastService

LOGGER = logging.getLogger(__name__)
NOTIFICATION_WINDOW_DURATION = timedelta(hours=1)


def run_once(
    force_mock: bool = False,
    force_notify: bool = False,
    now: datetime | None = None,
) -> int:
    config = load_config()
    setup_logging(config, quiet=True)
    state_store = StateStore()
    current_time = as_kst(now)
    state_store.update(last_checked_at=current_time.isoformat(timespec="seconds"), last_error=None)
    LOGGER.info("StarRestaurantRadar started.")

    try:
        if not force_notify and not is_within_notification_window(config, current_time):
            window_start, window_end = notification_window_bounds(config, current_time.date())
            message = (
                f"알림 가능 시간 아님: 오늘 {window_start:%H:%M}~{window_end:%H:%M}에만 자동 알림을 확인합니다."
            )
            LOGGER.info("Skip notification: %s", message)
            state_store.update(last_result=message)
            return 0

        today = current_time.date()
        holiday_service = HolidayService(config)
        should_run, reason = holiday_service.should_run(today)
        if not force_notify and not should_run:
            LOGGER.info("Skip notification: %s", reason)
            state_store.update(last_result=reason)
            return 0

        post = create_client(config, force_mock=force_mock).get_latest_post(config.instagram_username)
        if not post:
            message = "최신 게시물을 찾지 못함"
            LOGGER.info(message)
            state = state_store.load()
            cached_post = create_cached_post_from_state(config, state)
            if cached_post:
                cached, cached_image_path = cached_post
                if not force_notify and not is_today_post(cached, current_time):
                    state_store.update(
                        last_result="오늘 게시물임을 확인할 수 없는 이전 캐시이므로 자동 알림을 보내지 않음",
                        last_error=message,
                    )
                    return 0
                if (
                    not force_notify
                    and config.prevent_duplicate
                    and state.get("last_notified_post_id") == cached.post_id
                ):
                    state_store.update(
                        last_result="최신 게시물 조회 실패; 기존 이미지 캐시 유지",
                        last_permalink=cached.permalink,
                        last_image_path=str(cached_image_path),
                        last_error=message,
                    )
                    return 0
                result = ToastService(config).show_menu_notification(cached, cached_image_path)
                state_store.update(
                    last_notified_post_id=cached.post_id,
                    last_notified_at=iso_now(),
                    last_post_published_at=(
                        cached.published_at.isoformat(timespec="seconds") if cached.published_at else None
                    ),
                    last_permalink=cached.permalink,
                    last_image_path=str(cached_image_path),
                    last_result=f"{result} (기존 캐시 이미지)",
                    last_error=message,
                )
                return 0
            if config.fallback_link_only_notification:
                post = create_lookup_failure_post(config.instagram_username)
                if (
                    not force_notify
                    and config.prevent_duplicate
                    and state.get("last_notified_post_id") == post.post_id
                ):
                    state_store.update(last_result="조회 실패 링크 알림 이미 전송", last_permalink=post.permalink)
                    return 0
                result = ToastService(config).show_menu_notification(post, None)
                state_store.update(
                    last_notified_post_id=post.post_id,
                    last_notified_at=iso_now(),
                    last_permalink=post.permalink,
                    last_image_path=None,
                    last_result=result,
                    last_error=message,
                )
                return 0
            state_store.update(last_result=message)
            return 0

        if not force_notify and not is_today_post(post, current_time):
            message = "오늘 게시물이 아니므로 자동 알림을 보내지 않음"
            LOGGER.info("%s: %s", message, post.permalink)
            state_store.update(last_result=message, last_permalink=post.permalink)
            return 0

        state = state_store.load()
        if (
            not force_notify
            and config.prevent_duplicate
            and state.get("last_notified_post_id") == post.post_id
        ):
            message = "이미 알림을 보낸 게시물"
            LOGGER.info("%s: %s", message, post.post_id)
            state_store.update(last_result=message, last_permalink=post.permalink)
            return 0

        image_path = ImageCacheService(config).cache_post_image(
            post,
            allow_placeholder=force_mock or post.media_type == "mock",
        )
        if image_path is None and not config.fallback_link_only_notification:
            message = "이미지를 가져오지 못해 알림 중단"
            LOGGER.info(message)
            state_store.update(last_result=message, last_permalink=post.permalink)
            return 0

        result = ToastService(config).show_menu_notification(post, image_path)
        state_store.update(
            last_notified_post_id=post.post_id,
            last_notified_at=iso_now(),
            last_post_published_at=(post.published_at.isoformat(timespec="seconds") if post.published_at else None),
            last_permalink=post.permalink,
            last_image_path=str(image_path) if image_path else None,
            last_result=result,
        )
        LOGGER.info("StarRestaurantRadar finished: %s", result)
        return 0
    except Exception as exc:
        LOGGER.exception("Notifier failed.")
        state_store.update(last_result="오류 발생", last_error=str(exc))
        return 1


def as_kst(value: datetime | None = None) -> datetime:
    current = value or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    return current.astimezone(KST)


def notification_window_bounds(config: AppConfig, target_date: date) -> tuple[datetime, datetime]:
    hour, minute = (int(part) for part in config.notification_time.split(":"))
    window_start = datetime.combine(target_date, time(hour=hour, minute=minute), tzinfo=KST)
    end_of_day = datetime.combine(target_date, time.max, tzinfo=KST)
    window_end = min(window_start + NOTIFICATION_WINDOW_DURATION, end_of_day)
    return window_start, window_end


def is_within_notification_window(config: AppConfig, now: datetime | None = None) -> bool:
    current = as_kst(now)
    window_start, window_end = notification_window_bounds(config, current.date())
    return window_start <= current <= window_end


def is_today_post(post: InstagramPost, now: datetime | None = None) -> bool:
    if post.published_at is None:
        return False
    return post.published_at.astimezone(KST).date() == as_kst(now).date()


def create_lookup_failure_post(username: str) -> InstagramPost:
    today = datetime.now(KST).date()
    published_at = datetime.combine(today, time(hour=9), tzinfo=KST)
    clean_username = username.strip().lstrip("@") or "byeolsikdang"
    return InstagramPost(
        post_id=f"lookup-failed-{today:%Y%m%d}",
        shortcode=f"lookup-failed-{today:%Y%m%d}",
        permalink=f"https://www.instagram.com/{clean_username}/",
        image_url=None,
        thumbnail_url=None,
        caption="Instagram 최신 게시물 조회가 막혀 프로필 링크로 확인이 필요합니다.",
        published_at=published_at,
        media_type="lookup_failure",
    )


def create_cached_post_from_state(
    config: AppConfig,
    state: dict[str, object],
) -> tuple[InstagramPost, Path] | None:
    image_path = cached_image_path(config, state)
    if not image_path:
        return None

    shortcode = image_path.stem
    state_post_id = str(state.get("last_notified_post_id") or "")
    if is_plausible_shortcode(state_post_id) and state_post_id == shortcode:
        post_id = state_post_id
    else:
        post_id = shortcode
    if not is_plausible_shortcode(post_id):
        return None

    permalink = str(state.get("last_permalink") or "")
    if shortcode not in permalink:
        permalink = f"https://www.instagram.com/p/{post_id}/"

    published_at = None
    state_published_at = state.get("last_post_published_at")
    if isinstance(state_published_at, str):
        published_at = parse_datetime(state_published_at)
    return (
        InstagramPost(
            post_id=post_id,
            shortcode=post_id,
            permalink=permalink,
            image_url=None,
            thumbnail_url=None,
            caption="Instagram 조회가 막혀 최근 성공한 별식당 게시물 이미지를 다시 표시합니다.",
            published_at=published_at,
            media_type="cached_image",
        ),
        image_path,
    )


def cached_image_path(config: AppConfig, state: dict[str, object]) -> Path | None:
    state_image = state.get("last_image_path")
    if isinstance(state_image, str) and state_image:
        path = Path(state_image)
        if path.exists() and is_plausible_shortcode(path.stem):
            return path

    cache_dir = config.cache_path
    if not cache_dir.exists():
        return None
    candidates = [
        path
        for path in cache_dir.glob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and is_plausible_shortcode(path.stem)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


if __name__ == "__main__":
    raise SystemExit(run_once())
