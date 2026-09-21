"""앱 업데이트 - 등록자가 자기 앱을 새 버전으로 올립니다.

정한 것
  업데이트는 **바로 반영**됩니다. 올릴 때마다 관리자 승인을 다시 받게 하면
  개발자가 업데이트를 안 하게 되고, 그러면 고쳐진 앱이 사람들에게 가지
  않습니다. 대신 세 가지를 둡니다.
    1) 버전 이력이 남습니다 (누가 언제 무엇을 바꿨는지)
    2) 공식(approved) 앱이면 관리자에게 알림이 갑니다
    3) 문제가 있으면 이전 버전으로 되돌릴 수 있습니다

되돌리기가 진짜로 되는 이유
  GitHub/ZIP 으로 올린 소스는 버전마다 폴더를 따로 둡니다(packages.py).
  되돌리기는 앱이 가리키는 폴더를 옛 폴더로 바꾸는 일입니다.
  주소만 등록한 앱(manual)은 주소를 옛 주소로 되돌립니다.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from sqlalchemy.orm import Session

from app import notify, packages
from app.api.apps import _owned_or_403, _sync_tools, _visible_or_404
from app.api.packages import _apply_manifest
from app.audit import record
from app.db import get_db
from app.deps import current_user
from app.models import App, AppVersion, AppVisibility, SourceType
from app.schemas import AppOut, AppUpdateEndpointIn, AppVersionOut

router = APIRouter(tags=["앱 업데이트"])


def _ensure_baseline(db: Session, app: App) -> None:
    """이력이 한 줄도 없으면, 지금 상태를 '처음 등록된 상태'로 한 줄 남깁니다.

    이게 없으면 첫 업데이트 뒤에 되돌아갈 자리가 없습니다.
    """
    if db.query(AppVersion).filter(AppVersion.app_id == app.id).first():
        return
    db.add(
        AppVersion(
            app_id=app.id,
            version=app.package_version,
            note="처음 등록된 상태",
            endpoint=app.endpoint,
            source_type=app.source_type.value,
            source_url=app.source_url,
            package_path=app.package_path,
            tool_count=len(app.tools),
            is_current=True,
            created_by=app.owner_user_id,
            created_at=app.created_at,
        )
    )
    db.commit()


def _new_version(
    db: Session,
    app: App,
    note: str,
    user_id: str,
    source_ref: str = "",
    rolled_back_from: str = "",
) -> AppVersion:
    """지금 앱 상태를 '현재 버전'으로 한 줄 남깁니다(이력은 지우지 않고 쌓기만)."""
    for old in db.query(AppVersion).filter(
        AppVersion.app_id == app.id, AppVersion.is_current.is_(True)
    ):
        old.is_current = False

    row = AppVersion(
        app_id=app.id,
        version=app.package_version,
        note=note,
        endpoint=app.endpoint,
        source_type=app.source_type.value,
        source_url=app.source_url,
        source_ref=source_ref,
        package_path=app.package_path,
        tool_count=len(app.tools),
        is_current=True,
        rolled_back_from=rolled_back_from,
        created_by=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _announce(db: Session, app: App, version: AppVersion) -> None:
    """업데이트를 알려야 할 사람들에게 알립니다.

    - 이 앱을 카드에 담아 쓰는 사람들: 쓰던 게 바뀌었으니 알아야 합니다.
    - 공식 앱이면 관리자: 승인해 준 앱이 조용히 바뀌는 일이 없도록.
    """
    label = f"v{version.version}" if version.version else "새 버전"
    body = (version.note or "").strip() or "변경 내용이 적혀 있지 않습니다."

    targets = notify.card_user_ids(db, app.id) - {version.created_by}
    notify.send_many(
        db, targets, "app_updated",
        f"'{app.name}' 앱이 {label} 로 업데이트됐습니다", body, target_id=app.id,
    )

    if app.visibility == AppVisibility.approved:
        admins = notify.admin_ids(db) - {version.created_by} - targets
        notify.send_many(
            db, admins, "app_updated",
            f"공식 앱 '{app.name}' 이 {label} 로 업데이트됐습니다",
            f"{body}\n올린 사람: {version.created_by}", target_id=app.id,
        )


def _keep_paths(db: Session, app_id: str) -> set[str]:
    """되돌릴 수 있게 남겨 둬야 하는 소스 폴더들."""
    return {
        row.package_path
        for row in db.query(AppVersion).filter(AppVersion.app_id == app_id).all()
        if row.package_path
    }


# ------------------------------- 이력 보기 -------------------------------
@router.get(
    "/api/apps/{app_id}/versions", response_model=list[AppVersionOut],
    summary="앱 버전 이력",
)
def list_versions(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[AppVersion]:
    app = _visible_or_404(db, app_id, user_id)
    _ensure_baseline(db, app)
    return (
        db.query(AppVersion)
        .filter(AppVersion.app_id == app.id)
        .order_by(AppVersion.created_at.desc())
        .all()
    )


# ------------------------------- 업데이트 -------------------------------
@router.post(
    "/api/apps/{app_id}/update/endpoint", response_model=AppOut,
    summary="새 버전 올리기(주소만 등록한 앱)",
)
async def update_endpoint(
    app_id: str,
    payload: AppUpdateEndpointIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _owned_or_403(db, app_id, user_id)
    _ensure_baseline(db, app)

    app.endpoint = payload.endpoint
    if payload.version:
        app.package_version = payload.version
    db.commit()
    await _sync_tools(db, app)  # 바뀐 앱의 기능 목록을 다시 읽습니다

    version = _new_version(db, app, payload.note, user_id)
    _announce(db, app, version)
    record(db, user_id, "app_updated", "app", app.id,
           {"version": app.package_version, "source": "endpoint"}, request)
    return app


@router.post(
    "/api/apps/{app_id}/update/from-github", response_model=AppOut,
    summary="새 버전 올리기(GitHub 주소)",
)
async def update_from_github(
    app_id: str,
    request: Request,
    source_url: str = Form("", description="비우면 처음 등록한 주소를 그대로 씁니다"),
    ref: str = Form("", description="브랜치나 태그. 비우면 기본 브랜치"),
    note: str = Form("", description="무엇이 바뀌었는지"),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _owned_or_403(db, app_id, user_id)
    _ensure_baseline(db, app)

    url = source_url or app.source_url
    if not url:
        raise HTTPException(400, "받아올 GitHub 주소가 없습니다.")

    try:
        app_dir, manifest = packages.store_github(app.slug, url, ref)
    except packages.PackageError as exc:
        raise HTTPException(400, str(exc)) from exc

    app.source_type = SourceType.github
    app.source_url = url
    app.package_path = str(app_dir)
    _apply_manifest(app, manifest)
    db.commit()
    if app.endpoint:
        await _sync_tools(db, app)

    version = _new_version(db, app, note, user_id, source_ref=ref)
    packages.prune_versions(app.slug, keep=_keep_paths(db, app.id))
    _announce(db, app, version)
    record(db, user_id, "app_updated", "app", app.id,
           {"version": app.package_version, "source": "github", "ref": ref}, request)
    return app


@router.post(
    "/api/apps/{app_id}/update/from-zip", response_model=AppOut,
    summary="새 버전 올리기(ZIP 파일)",
)
async def update_from_zip(
    app_id: str,
    request: Request,
    file: UploadFile = File(..., description="어댑터 폴더를 통째로 압축한 ZIP"),
    note: str = Form("", description="무엇이 바뀌었는지"),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _owned_or_403(db, app_id, user_id)
    _ensure_baseline(db, app)

    with tempfile.TemporaryDirectory() as tmp:
        temp_path = Path(tmp) / (file.filename or "upload.zip")
        with temp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        try:
            app_dir, manifest = packages.store_zip(app.slug, temp_path)
        except packages.PackageError as exc:
            raise HTTPException(400, str(exc)) from exc

    app.source_type = SourceType.zip
    app.package_path = str(app_dir)
    _apply_manifest(app, manifest)
    db.commit()
    if app.endpoint:
        await _sync_tools(db, app)

    version = _new_version(db, app, note, user_id)
    packages.prune_versions(app.slug, keep=_keep_paths(db, app.id))
    _announce(db, app, version)
    record(db, user_id, "app_updated", "app", app.id,
           {"version": app.package_version, "source": "zip"}, request)
    return app


# ------------------------------- 되돌리기 -------------------------------
@router.post(
    "/api/apps/{app_id}/versions/{version_id}/rollback", response_model=AppOut,
    summary="이전 버전으로 되돌리기",
)
async def rollback(
    app_id: str,
    version_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _owned_or_403(db, app_id, user_id)
    target = db.get(AppVersion, version_id)
    if target is None or target.app_id != app.id:
        raise HTTPException(404, "그 버전 기록을 찾을 수 없습니다.")
    if target.is_current:
        raise HTTPException(400, "지금 쓰고 있는 버전입니다.")
    if target.package_path and not Path(target.package_path).is_dir():
        raise HTTPException(
            400, "그 버전의 소스 폴더가 서버에 남아 있지 않아 되돌릴 수 없습니다."
        )

    app.endpoint = target.endpoint
    app.source_type = SourceType(target.source_type)
    app.source_url = target.source_url
    app.package_path = target.package_path
    app.package_version = target.version
    db.commit()
    if app.endpoint:
        await _sync_tools(db, app)

    label = f"v{target.version}" if target.version else "이전 버전"
    version = _new_version(
        db, app, f"{label} 으로 되돌림", user_id,
        source_ref=target.source_ref, rolled_back_from=target.id,
    )
    _announce(db, app, version)
    record(db, user_id, "app_rolled_back", "app", app.id,
           {"to_version": target.version, "version_id": target.id}, request)
    return app
