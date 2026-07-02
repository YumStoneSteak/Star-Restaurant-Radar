from __future__ import annotations

import html
import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from config import AppConfig

LOGGER = logging.getLogger(__name__)
try:
    KST = ZoneInfo("Asia/Seoul")
except ZoneInfoNotFoundError:
    KST = timezone(timedelta(hours=9), name="Asia/Seoul")


@dataclass
class InstagramPost:
    post_id: str
    shortcode: str
    permalink: str
    image_url: str | None
    thumbnail_url: str | None
    caption: str
    published_at: datetime | None
    media_type: str


class InstagramClientError(RuntimeError):
    pass


class InstagramClient:
    def get_latest_post(self, username: str) -> InstagramPost | None:
        raise NotImplementedError


class MockInstagramClient(InstagramClient):
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def get_latest_post(self, username: str) -> InstagramPost:
        today = datetime.now(KST).date()
        published_at = datetime.combine(today, time(hour=9), tzinfo=KST)
        shortcode = f"mock-{today:%Y%m%d}"
        permalink = self.config.test_post_url or f"https://www.instagram.com/p/{shortcode}/"
        return InstagramPost(
            post_id=shortcode,
            shortcode=shortcode,
            permalink=permalink,
            image_url=self.config.test_image_url or None,
            thumbnail_url=self.config.test_image_url or None,
            caption="오늘의 별식당 메뉴 테스트 게시물",
            published_at=published_at,
            media_type="mock",
        )


class WebInstagramClient(InstagramClient):
    PROFILE_URL = "https://www.instagram.com/{username}/"
    PROFILE_API_URL = "https://www.instagram.com/api/v1/users/web_profile_info/?{query}"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    def __init__(self, config: AppConfig | None = None, timeout_seconds: int = 12) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def get_latest_post(self, username: str) -> InstagramPost | None:
        username = username.strip().lstrip("@")
        if not username:
            raise InstagramClientError("인스타그램 사용자 이름이 비어 있습니다.")

        api_post = self._get_latest_from_profile_api(username)
        if api_post:
            return api_post

        rendered_post = self._get_latest_from_rendered_grid(username)
        if rendered_post:
            return rendered_post

        profile_url = self.PROFILE_URL.format(username=username)
        profile_html = self._fetch_text(profile_url)
        shortcode = self._extract_latest_shortcode(profile_html)
        if not shortcode:
            raise InstagramClientError("공개 프로필에서 최신 게시물 정보를 찾지 못했습니다.")

        permalink = f"https://www.instagram.com/p/{shortcode}/"
        post_html = self._fetch_text(permalink)
        return InstagramPost(
            post_id=shortcode,
            shortcode=shortcode,
            permalink=permalink,
            image_url=self._extract_meta(post_html, "og:image"),
            thumbnail_url=self._extract_meta(post_html, "og:image"),
            caption=self._extract_caption(post_html),
            published_at=self._extract_published_at(post_html),
            media_type=self._extract_media_type(post_html),
        )

    def _get_latest_from_rendered_grid(self, username: str) -> InstagramPost | None:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError:
            LOGGER.info("Playwright is not installed; rendered grid lookup is skipped.")
            return None

        profile_url = self.PROFILE_URL.format(username=username)
        try:
            with sync_playwright() as playwright:
                context, browser = self._create_browser_context(playwright, headless=True)
                page = context.new_page()
                page.goto(profile_url, wait_until="domcontentloaded", timeout=25_000)
                page.wait_for_timeout(4_000)
                if "/accounts/login/" in page.url:
                    LOGGER.info("Rendered Instagram profile redirected to login; login session is required.")
                    context.close()
                    if browser:
                        browser.close()
                    return None
                grid_item = page.evaluate(
                    """
                    () => {
                        const anchors = Array.from(document.querySelectorAll('a[href]'));
                        const postLinks = anchors
                            .filter((anchor) => /^\\/(p|reel)\\//.test(anchor.getAttribute('href') || ''))
                            .concat(anchors.filter((anchor) => /^\\/[^/]+\\/(p|reel)\\//.test(anchor.getAttribute('href') || '')))
                            .filter((anchor) => {
                                const rect = anchor.getBoundingClientRect();
                                return rect.width > 40 && rect.height > 40;
                            });
                        const anchor = postLinks[0];
                        if (!anchor) return null;
                        const img = anchor.querySelector('img');
                        return {
                            href: anchor.href,
                            image: img ? img.currentSrc || img.src : null,
                            caption: img ? img.alt || '' : ''
                        };
                    }
                    """
                )
                if not grid_item:
                    context.close()
                    if browser:
                        browser.close()
                    return None

                permalink = str(grid_item.get("href") or "")
                image_url = grid_item.get("image") or None
                caption = str(grid_item.get("caption") or "별식당 최신 게시물")
                shortcode = shortcode_from_permalink(permalink)
                if not shortcode:
                    context.close()
                    if browser:
                        browser.close()
                    return None

                published_at = self._read_post_time_from_browser(context, permalink)
                context.close()
                if browser:
                    browser.close()

                return InstagramPost(
                    post_id=shortcode,
                    shortcode=shortcode,
                    permalink=permalink,
                    image_url=image_url,
                    thumbnail_url=image_url,
                    caption=caption,
                    published_at=published_at,
                    media_type="rendered_grid",
                )
        except (PlaywrightError, PlaywrightTimeoutError, OSError) as exc:
            LOGGER.info("Rendered Instagram grid lookup failed: %s", exc)
            return None

    def _create_browser_context(self, playwright, headless: bool):  # type: ignore[no-untyped-def]
        if self.config and self.config.use_instagram_login_session:
            session_path = runtime_instagram_session_path(self.config)
            session_path.mkdir(parents=True, exist_ok=True)
            try:
                launch_options = {
                    "user_data_dir": str(session_path),
                    "headless": headless,
                    "locale": "ko-KR",
                    "timezone_id": "Asia/Seoul",
                    "user_agent": self.USER_AGENT,
                    "viewport": {"width": 1280, "height": 1000},
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--disable-extensions",
                    ],
                }
                chrome_path = find_chrome_executable()
                if chrome_path:
                    launch_options["executable_path"] = chrome_path
                else:
                    launch_options["channel"] = "chrome"
                context = playwright.chromium.launch_persistent_context(
                    **launch_options,
                )
                return context, None
            except Exception as exc:
                LOGGER.info("Persistent Instagram session launch failed: %s", exc)

        browser = self._launch_browser(playwright, headless=headless)
        context = browser.new_context(
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            user_agent=self.USER_AGENT,
            viewport={"width": 1280, "height": 1000},
        )
        return context, browser

    def _launch_browser(self, playwright, headless: bool):  # type: ignore[no-untyped-def]
        launch_args = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-extensions",
            ],
        }
        try:
            chrome_path = find_chrome_executable()
            if chrome_path:
                return playwright.chromium.launch(executable_path=chrome_path, **launch_args)
            return playwright.chromium.launch(channel="chrome", **launch_args)
        except Exception:
            return playwright.chromium.launch(**launch_args)

    def _read_post_time_from_browser(self, context, permalink: str) -> datetime | None:  # type: ignore[no-untyped-def]
        try:
            page = context.new_page()
            page.goto(permalink, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(2_000)
            value = page.locator("time[datetime]").first.get_attribute("datetime", timeout=5_000)
            page.close()
            return parse_datetime(value)
        except Exception:
            LOGGER.info("Could not read rendered post timestamp from %s", permalink)
            return None

    def _get_latest_from_profile_api(self, username: str) -> InstagramPost | None:
        url = self.PROFILE_API_URL.format(query=urlencode({"username": username}))
        request = Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
                "x-ig-app-id": "936619743392459",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            LOGGER.info("Instagram profile API lookup failed: %s", exc)
            return None

        try:
            edges = data["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
            node = edges[0]["node"]
        except (KeyError, IndexError, TypeError):
            return None

        shortcode = str(node.get("shortcode") or "")
        if not is_plausible_shortcode(shortcode):
            return None

        caption = ""
        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        if caption_edges:
            caption = caption_edges[0].get("node", {}).get("text", "") or ""

        timestamp = node.get("taken_at_timestamp")
        published_at = None
        if isinstance(timestamp, int):
            published_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(KST)

        image_url = node.get("display_url") or node.get("thumbnail_src")
        return InstagramPost(
            post_id=str(node.get("id") or shortcode),
            shortcode=shortcode,
            permalink=f"https://www.instagram.com/p/{shortcode}/",
            image_url=image_url,
            thumbnail_url=node.get("thumbnail_src") or image_url,
            caption=caption or "별식당 최신 게시물",
            published_at=published_at,
            media_type=str(node.get("__typename") or "image"),
        )

    def _fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "text/html"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                return raw.decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise InstagramClientError(f"{url}을 불러오지 못했습니다: {exc}") from exc

    def _extract_latest_shortcode(self, document: str) -> str | None:
        patterns = [
            r'"shortcode"\s*:\s*"([^"]+)"',
            r'href="(/p/([^/"]+)/)"',
            r'\\?/p\\?/([^\\?/"]+)\\?/',
        ]
        for pattern in patterns:
            match = re.search(pattern, document)
            if match:
                shortcode = match.group(match.lastindex or 1).strip("/")
                if is_plausible_shortcode(shortcode):
                    return shortcode
        return None

    def _extract_meta(self, document: str, property_name: str) -> str | None:
        pattern = (
            rf'<meta[^>]+property=["\']{re.escape(property_name)}["\'][^>]+content=["\']([^"\']+)["\']'
            rf'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(property_name)}["\']'
        )
        match = re.search(pattern, document, flags=re.IGNORECASE)
        if not match:
            return None
        value = match.group(1) or match.group(2)
        return html.unescape(value)

    def _extract_caption(self, document: str) -> str:
        description = self._extract_meta(document, "og:description")
        if description:
            return description
        return "별식당 최신 게시물"

    def _extract_published_at(self, document: str) -> datetime | None:
        json_ld = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            document,
            flags=re.DOTALL | re.IGNORECASE,
        )
        for block in json_ld:
            try:
                data = json.loads(html.unescape(block))
            except json.JSONDecodeError:
                continue
            date_value = self._find_date_published(data)
            parsed = parse_datetime(date_value)
            if parsed:
                return parsed

        match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', document)
        return parse_datetime(match.group(1)) if match else None

    def _find_date_published(self, value: object) -> str | None:
        if isinstance(value, dict):
            if isinstance(value.get("datePublished"), str):
                return value["datePublished"]
            for child in value.values():
                found = self._find_date_published(child)
                if found:
                    return found
        if isinstance(value, list):
            for child in value:
                found = self._find_date_published(child)
                if found:
                    return found
        return None

    def _extract_media_type(self, document: str) -> str:
        media_type = self._extract_meta(document, "og:type") or "image"
        return media_type.replace("instapp:", "")


class AutoInstagramClient(InstagramClient):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.web_client = WebInstagramClient(config)
        self.mock_client = MockInstagramClient(config)

    def get_latest_post(self, username: str) -> InstagramPost | None:
        try:
            return self.web_client.get_latest_post(username)
        except InstagramClientError:
            LOGGER.exception("Web Instagram lookup failed.")
            if self.config.mock_on_web_failure or self.config.test_post_url or self.config.test_image_url:
                LOGGER.info("Using mock post fallback because mock fallback/test values are configured.")
                return self.mock_client.get_latest_post(username)
            return None


def parse_datetime(value: Optional[str]) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def is_plausible_shortcode(value: str) -> bool:
    if value in {"en_US", "ko_KR"}:
        return False
    if not 5 <= len(value) <= 32:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]+", value))


def shortcode_from_permalink(permalink: str) -> str | None:
    parsed = urlparse(permalink)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"p", "reel"} and is_plausible_shortcode(parts[1]):
        return parts[1]
    if len(parts) >= 3 and parts[1] in {"p", "reel"} and is_plausible_shortcode(parts[2]):
        return parts[2]
    return None


def create_client(config: AppConfig, force_mock: bool = False) -> InstagramClient:
    if force_mock or config.client_mode == "mock":
        return MockInstagramClient(config)
    if config.client_mode == "web":
        return WebInstagramClient(config)
    return AutoInstagramClient(config)


def create_login_session(config: AppConfig) -> subprocess.Popen:
    username = config.instagram_username.strip().lstrip("@") or "byeolsikdang"
    config.instagram_session_path.mkdir(parents=True, exist_ok=True)
    profile_url = WebInstagramClient.PROFILE_URL.format(username=username)
    chrome_path = find_chrome_executable()
    if not chrome_path:
        raise InstagramClientError("Chrome 또는 Microsoft Edge 실행 파일을 찾지 못했습니다. Chrome 또는 Edge 설치 후 다시 시도해 주세요.")

    command = [
        chrome_path,
        f"--user-data-dir={config.instagram_session_path}",
        "--new-window",
        "--no-first-run",
        profile_url,
    ]
    creationflags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )


SESSION_COPY_SKIP_DIRS = {
    "browsermetrics",
    "cache",
    "cachestorage",
    "code cache",
    "crashpad",
    "dawncache",
    "file system",
    "gpucache",
    "graphitedawncache",
    "grshadercache",
    "indexeddb",
    "session storage",
    "service worker",
    "shadercache",
}


def runtime_instagram_session_path(config: AppConfig) -> Path:
    source_path = config.instagram_session_path
    source_path.mkdir(parents=True, exist_ok=True)
    runtime_path = source_path.with_name(f"{source_path.name}_runtime")
    if not any(source_path.iterdir()):
        return source_path

    try:
        refresh_runtime_instagram_session(source_path, runtime_path)
        return runtime_path
    except Exception as exc:
        LOGGER.info("Could not prepare Instagram runtime session copy: %s", exc)
        return source_path


def refresh_runtime_instagram_session(source_path: Path, runtime_path: Path) -> None:
    source = source_path.resolve()
    runtime = runtime_path.resolve()
    if runtime == source or runtime.parent != source.parent or not runtime.name.endswith("_runtime"):
        raise InstagramClientError("인스타그램 임시 세션 경로가 안전하지 않습니다.")

    if runtime.exists():
        shutil.rmtree(runtime, ignore_errors=True)
    runtime.mkdir(parents=True, exist_ok=True)

    for root, dir_names, file_names in os.walk(source):
        root_path = Path(root)
        relative_root = root_path.relative_to(source)
        dir_names[:] = [
            name
            for name in dir_names
            if not should_skip_session_copy_item(root_path / name, is_dir=True)
        ]
        target_root = runtime / relative_root
        try:
            target_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            LOGGER.debug("Skipped Instagram session directory %s: %s", root_path, exc)
            dir_names[:] = []
            continue

        for file_name in file_names:
            source_file = root_path / file_name
            if should_skip_session_copy_item(source_file, is_dir=False):
                continue
            target_file = target_root / file_name
            try:
                shutil.copy2(source_file, target_file)
            except OSError as exc:
                LOGGER.debug("Skipped locked Instagram session file %s: %s", source_file, exc)


def should_skip_session_copy_item(path: Path, is_dir: bool) -> bool:
    name = path.name
    lower_name = name.lower()
    if lower_name.startswith("singleton"):
        return True
    if is_dir:
        return lower_name in SESSION_COPY_SKIP_DIRS
    return lower_name in {"lock", "lockfile"} or lower_name.endswith("-journal") or lower_name.endswith(".tmp")


def find_chrome_executable() -> str | None:
    candidates = [
        os.environ.get("CHROME"),
        os.environ.get("CHROME_PATH"),
        os.environ.get("EDGE"),
        os.environ.get("MSEDGE"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path.home() / r"AppData\Local\Microsoft\Edge\Application\msedge.exe",
    ]
    candidates.extend(browser_paths_from_registry())
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def browser_paths_from_registry() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    paths: list[Path] = []
    app_path_keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"),
    ]
    for hive, key_path in app_path_keys:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _value_type = winreg.QueryValueEx(key, "")
        except OSError:
            continue
        if value:
            paths.append(Path(str(value)))
    return paths


def _profile_grid_visible(page) -> bool:  # type: ignore[no-untyped-def]
    try:
        return bool(
            page.evaluate(
                """
                () => Array.from(document.querySelectorAll('a[href]'))
                    .some((anchor) => {
                        const href = anchor.getAttribute('href') || '';
                        return /^\\/(p|reel)\\//.test(href) || /^\\/[^/]+\\/(p|reel)\\//.test(href);
                    })
                """
            )
        )
    except Exception:
        return False
