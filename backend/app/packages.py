"""앱 패키지 받기 - GitHub 주소 또는 ZIP 업로드.

개발자는 어댑터 코드를 통째로 올리고, 서버가 그것을 보관합니다.
서버 구동형이면 서버가 직접 띄우고, PC 구동형이면 Launcher 가 받아 갑니다.

패키지 안에는 workflow_app.json (매니페스트) 이 있어야 합니다.
형식은 docs/WRAPPER_SPEC.md 참고.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import zipfile
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MANIFEST_NAME = "workflow_app.json"
MAX_UNPACKED_BYTES = 200 * 1024 * 1024  # 200MB


class PackageError(Exception):
    """패키지를 받지 못했을 때. 사용자에게 그대로 보여 줄 메시지입니다."""


def packages_root() -> Path:
    path = Path(settings.data_dir) / "packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_extract(zip_path: Path, target: Path) -> None:
    """ZIP 을 풉니다.

    악의적인 ZIP 이 '../../etc/passwd' 같은 경로를 넣어 target 바깥에 파일을
    쓰는 공격(Zip Slip)이 있어서, 풀기 전에 경로를 하나씩 검사합니다.
    """
    with zipfile.ZipFile(zip_path) as archive:
        total = sum(info.file_size for info in archive.infolist())
        if total > MAX_UNPACKED_BYTES:
            raise PackageError(
                f"압축을 풀면 {total // 1024 // 1024}MB 라 너무 큽니다(최대 200MB)."
            )

        target_resolved = target.resolve()
        for info in archive.infolist():
            destination = (target / info.filename).resolve()
            if not destination.is_relative_to(target_resolved):
                raise PackageError(f"허용되지 않는 경로가 들어 있습니다: {info.filename}")
        archive.extractall(target)


def _find_manifest(root: Path) -> tuple[Path, dict]:
    """매니페스트를 찾습니다. ZIP 안에 폴더가 한 겹 더 있어도 찾아 줍니다."""
    candidates = [root / MANIFEST_NAME, *sorted(root.glob(f"*/{MANIFEST_NAME}"))]
    for candidate in candidates:
        if candidate.is_file():
            try:
                return candidate.parent, json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise PackageError(f"{MANIFEST_NAME} 형식이 잘못되었습니다: {exc}") from exc
    raise PackageError(
        f"패키지 안에 {MANIFEST_NAME} 이 없습니다. "
        "docs/WRAPPER_SPEC.md 의 매니페스트 예시를 참고해 주세요."
    )


def store_zip(slug: str, zip_path: Path) -> tuple[Path, dict]:
    """업로드된 ZIP 을 풀어 보관하고 (앱 폴더, 매니페스트) 를 돌려줍니다."""
    target = packages_root() / slug
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    try:
        _safe_extract(zip_path, target)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise PackageError("ZIP 파일을 열 수 없습니다.") from exc
    except PackageError:
        shutil.rmtree(target, ignore_errors=True)
        raise

    try:
        return _find_manifest(target)
    except PackageError:
        shutil.rmtree(target, ignore_errors=True)
        raise


def store_github(slug: str, url: str, ref: str = "") -> tuple[Path, dict]:
    """GitHub(사내 Git 포함) 주소에서 받아 보관합니다."""
    if not url.startswith(("https://", "http://", "git@")):
        raise PackageError("https:// 또는 git@ 로 시작하는 주소만 받습니다.")

    target = packages_root() / slug
    if target.exists():
        shutil.rmtree(target)

    command = ["git", "clone", "--depth", "1"]
    if ref:
        command += ["--branch", ref]
    command += [url, str(target)]

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=180, shell=False
        )
    except FileNotFoundError as exc:
        raise PackageError("서버에 git 이 설치되어 있지 않습니다.") from exc
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise PackageError("받아오는 데 너무 오래 걸려 중단했습니다.") from exc

    if completed.returncode != 0:
        shutil.rmtree(target, ignore_errors=True)
        raise PackageError(f"받아오지 못했습니다: {(completed.stderr or '').strip()[:300]}")

    try:
        return _find_manifest(target)
    except PackageError:
        shutil.rmtree(target, ignore_errors=True)
        raise


def read_manifest(app_dir: str) -> dict:
    path = Path(app_dir) / MANIFEST_NAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
