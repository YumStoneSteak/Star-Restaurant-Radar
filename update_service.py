from __future__ import annotations

import hashlib
import json
import re
import ssl
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import APP_PRODUCT_NAME, APP_VERSION, GITHUB_REPO

try:
    import certifi as certifi_provider
except ImportError:  # pragma: no cover - dependency is packaged, fallback keeps source runs usable.
    try:
        from pip._vendor import certifi as certifi_provider  # type: ignore[no-redef]
    except ImportError:
        certifi_provider = None  # type: ignore[assignment]

GITHUB_API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
INSTALLER_NAME_RE = re.compile(r"StarRestaurantRadar-Setup-v\d+\.\d+\.\d+\.exe$", re.IGNORECASE)


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    browser_download_url: str
    size: int = 0


@dataclass(frozen=True)
class UpdateInfo:
    tag_name: str
    version: str
    html_url: str
    installer_asset: ReleaseAsset
    checksum_asset: ReleaseAsset | None


def check_for_update(current_version: str = APP_VERSION) -> UpdateInfo | None:
    release = fetch_latest_release()
    update = parse_latest_release(release)
    if not update:
        return None
    if is_newer_version(update.version, current_version):
        return update
    return None


def fetch_latest_release(timeout: int = 20) -> dict[str, object]:
    request = Request(
        GITHUB_API_LATEST_RELEASE,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{APP_PRODUCT_NAME}/{APP_VERSION}",
        },
    )
    try:
        with open_https(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("GitHub 릴리즈를 찾지 못했습니다.") from exc
        raise UpdateError(f"GitHub 릴리즈 조회 실패: HTTP {exc.code}") from exc
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        if is_certificate_verify_error(exc):
            raise UpdateError(
                "GitHub 릴리즈 조회 실패: 인증서 검증에 실패했습니다. "
                "앱에 포함된 인증서 묶음으로 다시 시도하도록 수정되었습니다. "
                "문제가 계속되면 Windows 날짜/시간 또는 보안 프로그램의 HTTPS 검사를 확인해 주세요."
            ) from exc
        raise UpdateError(f"GitHub 릴리즈 조회 실패: {exc}") from exc


def parse_latest_release(release: dict[str, object]) -> UpdateInfo | None:
    tag_name = str(release.get("tag_name") or "")
    version = normalize_version(tag_name)
    if not version:
        return None

    raw_assets = release.get("assets")
    if not isinstance(raw_assets, list):
        raw_assets = []
    assets = [
        ReleaseAsset(
            name=str(asset.get("name") or ""),
            browser_download_url=str(asset.get("browser_download_url") or ""),
            size=int(asset.get("size") or 0),
        )
        for asset in raw_assets
        if isinstance(asset, dict)
    ]
    installer_asset = select_installer_asset(assets)
    if not installer_asset:
        raise UpdateError("릴리즈에서 NSIS 설치 파일을 찾지 못했습니다.")

    return UpdateInfo(
        tag_name=tag_name,
        version=version,
        html_url=str(release.get("html_url") or ""),
        installer_asset=installer_asset,
        checksum_asset=select_checksum_asset(assets, installer_asset.name),
    )


def select_installer_asset(assets: list[ReleaseAsset]) -> ReleaseAsset | None:
    exact = [asset for asset in assets if INSTALLER_NAME_RE.fullmatch(asset.name)]
    if exact:
        return sorted(exact, key=lambda asset: asset.name)[-1]
    candidates = [
        asset
        for asset in assets
        if asset.name.lower().endswith(".exe") and "setup" in asset.name.lower() and "radar" in asset.name.lower()
    ]
    return sorted(candidates, key=lambda asset: asset.name)[-1] if candidates else None


def select_checksum_asset(assets: list[ReleaseAsset], installer_name: str) -> ReleaseAsset | None:
    expected_name = f"{installer_name}.sha256"
    for asset in assets:
        if asset.name.lower() == expected_name.lower():
            return asset
    for asset in assets:
        if asset.name.lower().endswith(".sha256"):
            return asset
    return None


def is_newer_version(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def normalize_version(value: str) -> str:
    value = value.strip()
    if value.startswith(("v", "V")):
        value = value[1:]
    value = value.split("-", 1)[0].split("+", 1)[0]
    return value if re.fullmatch(r"\d+\.\d+\.\d+", value) else ""


def parse_version(value: str) -> tuple[int, int, int]:
    normalized = normalize_version(value)
    if not normalized:
        raise UpdateError(f"버전 형식이 올바르지 않습니다: {value}")
    return tuple(int(part) for part in normalized.split("."))  # type: ignore[return-value]


def download_update_installer(update: UpdateInfo) -> Path:
    update_dir = Path(tempfile.gettempdir()) / "StarRestaurantRadarUpdate" / update.tag_name
    update_dir.mkdir(parents=True, exist_ok=True)
    installer_path = update_dir / update.installer_asset.name
    download_asset(update.installer_asset, installer_path)

    if update.checksum_asset:
        checksum_path = update_dir / update.checksum_asset.name
        download_asset(update.checksum_asset, checksum_path)
        verify_sha256_file(installer_path, checksum_path.read_text(encoding="utf-8"))
    return installer_path


def download_asset(asset: ReleaseAsset, target_path: Path, timeout: int = 60) -> None:
    if not asset.browser_download_url:
        raise UpdateError(f"다운로드 URL이 비어 있습니다: {asset.name}")
    request = Request(asset.browser_download_url, headers={"User-Agent": f"{APP_PRODUCT_NAME}/{APP_VERSION}"})
    try:
        with open_https(request, timeout=timeout) as response:
            data = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        if is_certificate_verify_error(exc):
            raise UpdateError(
                f"다운로드 실패: {asset.name}: 인증서 검증에 실패했습니다. "
                "Windows 날짜/시간 또는 보안 프로그램의 HTTPS 검사를 확인해 주세요."
            ) from exc
        raise UpdateError(f"다운로드 실패: {asset.name}: {exc}") from exc
    try:
        target_path.write_bytes(data)
    except OSError as exc:
        raise UpdateError(f"다운로드 파일을 저장하지 못했습니다: {target_path}") from exc


def verify_sha256_file(path: Path, checksum_text: str) -> None:
    expected = extract_sha256(checksum_text)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual.lower() != expected.lower():
        raise UpdateError("설치 파일 SHA256 검증에 실패했습니다.")


def extract_sha256(checksum_text: str) -> str:
    match = re.search(r"\b[a-fA-F0-9]{64}\b", checksum_text)
    if not match:
        raise UpdateError("SHA256 파일에서 해시 값을 찾지 못했습니다.")
    return match.group(0)


def install_update(installer_path: Path) -> subprocess.Popen:
    if not installer_path.exists():
        raise UpdateError(f"설치 파일이 없습니다: {installer_path}")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [str(installer_path), "/S", "/LAUNCH=1"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )


def running_from_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def open_https(request: Request, timeout: int):
    return urlopen(request, timeout=timeout, context=create_ssl_context())


def create_ssl_context() -> ssl.SSLContext:
    if certifi_provider:
        return ssl.create_default_context(cafile=certifi_provider.where())
    return ssl.create_default_context()


def is_certificate_verify_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)
