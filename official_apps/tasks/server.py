"""할 일/수명업무 앱 실행 파일.

한 프로세스가 두 가지를 같이 띄웁니다.
  /mcp   - 오케스트레이터가 부르는 MCP 주소 (Wrapper 규약)
  /api/* - 사용자가 보는 화면(Next.js)이 부르는 주소

실행:  python server.py   ->  http://localhost:9103/mcp
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import store
from mcp_adapter import mcp


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init()
    # MCP 세션 관리자를 같은 프로세스에서 돌립니다.
    async with mcp.session_manager.run():
        yield


api = FastAPI(title="할 일/수명업무 앱", lifespan=lifespan)

# 집에서 개발할 때 화면(3000번)에서 바로 부를 수 있게 열어 둡니다.
# 사내 배포 시에는 실제 화면 주소로 좁히세요.
api.add_middleware(
    CORSMiddleware,
    allow_origins=(os.getenv("ALLOW_ORIGINS", "*").split(",")),
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskIn(BaseModel):
    title: str
    owner: str = ""
    owner_email: str = ""
    due: str = ""
    note: str = ""
    kind: str = "task"
    orderer: str = ""


@api.get("/api/tasks", summary="할 일 목록")
def list_tasks(owner: str = "", status: str = "open", kind: str = "all", limit: int = 100) -> dict:
    items = store.search(owner=owner, status=status, kind=kind, limit=limit)
    return {"count": len(items), "tasks": items}


@api.post("/api/tasks", summary="할 일 추가")
def add_task(payload: TaskIn) -> dict:
    return store.add(
        title=payload.title,
        owner=payload.owner,
        owner_email=payload.owner_email,
        due=payload.due,
        note=payload.note,
        kind=payload.kind,
        orderer=payload.orderer,
    )


@api.post("/api/tasks/{task_id}/complete", summary="완료 처리")
def complete_task(task_id: str) -> dict:
    task = store.complete(task_id)
    return {"ok": task is not None, "task": task}


@api.get("/api/tasks/due-soon", summary="기한 임박/지연 목록")
def due_soon(days: int = 3, owner: str = "") -> dict:
    items = store.due_soon(days=days, owner=owner)
    return {"count": len(items), "tasks": items}


@api.get("/api/health", summary="살아있나 확인")
def health() -> dict:
    return {"status": "ok", "app": "task-tracker"}


# MCP 주소를 /mcp 에 붙입니다. 오케스트레이터는 이 주소만 압니다.
api.mount("/mcp", mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(api, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "9103")))
