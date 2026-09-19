"""FastAPI 진입점.  API 문서는 브라우저에서 http://localhost:8000/docs"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    apps,
    audit,
    auth,
    cards,
    dashboard,
    forms,
    health,
    launchers,
    notifications,
    packages,
    recipes,
    runs,
    schedules,
    stats,
    tools,
)
from app.config import get_settings
from app.db import SessionLocal, create_all
from app.health_monitor import run_forever
from app.scheduler.service import rearm_all
from app.seed import seed_from_file, seed_bootstrap_admin

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        create_all()
    seed_bootstrap_admin()
    if settings.seed_file:
        await seed_from_file(settings.seed_file)

    # 서버가 내려가 있는 동안에도 예약이 사라지지 않도록 전부 다시 걸어 둡니다.
    db = SessionLocal()
    try:
        rearm_all(db)
    except Exception as exc:  # Redis 가 아직 안 떴어도 서버는 떠야 합니다
        logger.warning("예약을 다시 거는 데 실패했습니다: %s", exc)
    finally:
        db.close()

    # 앱이 살아 있는지 주기적으로 확인하는 일꾼을 백그라운드로 띄웁니다.
    monitor = asyncio.create_task(run_forever())
    try:
        yield
    finally:
        monitor.cancel()


app = FastAPI(
    title="Workflow Auto",
    version="0.3.0",
    description=(
        "자연어 요청을 오케스트레이터가 분석해, 앱스토어에 등록된 "
        "개발자 앱(MCP 서버)들을 호출하고 결과를 합쳐 최종 산출물을 만듭니다."
    ),
    lifespan=lifespan,
)

# 사내 배포 시에는 allow_origins 를 실제 프론트 주소로 좁히세요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(apps.router)
app.include_router(packages.router)
app.include_router(cards.router)
app.include_router(runs.router)
app.include_router(recipes.router)
app.include_router(schedules.router)
app.include_router(dashboard.router)
app.include_router(forms.router)
app.include_router(launchers.router)
app.include_router(notifications.router)
app.include_router(stats.router)
app.include_router(tools.router)
app.include_router(audit.router)
