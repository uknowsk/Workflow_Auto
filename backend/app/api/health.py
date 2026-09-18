"""상태 점검 - 설치 후 '잘 떴나' 확인하는 용도."""
from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.worker.queue import get_queue, get_redis

router = APIRouter(tags=["상태"])
settings = get_settings()


@router.get("/health", summary="헬스체크")
def health() -> dict:
    checks: dict[str, str] = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        get_redis().ping()
        checks["redis"] = "ok"
        checks["queued_jobs"] = str(len(get_queue()))
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # LLM 은 실제로 부르지 않고 설정값만 보여줍니다(키는 노출하지 않습니다).
    checks["llm_base_url"] = settings.llm_base_url
    checks["llm_model"] = settings.llm_model
    checks["llm_tool_mode"] = settings.llm_tool_mode

    healthy = all(not v.startswith("error") for v in checks.values())
    return {"status": "ok" if healthy else "degraded", "checks": checks}
