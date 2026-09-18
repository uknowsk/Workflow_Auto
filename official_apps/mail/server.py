"""사내 메일 앱 실행 파일.

  /mcp   - 오케스트레이터가 부르는 MCP 주소
  /api/* - 화면(메일함)이 부르는 주소

실행:  python server.py   ->  http://localhost:9101/mcp
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import mcp_adapter
import store
from adapters import get_adapter
from mcp_adapter import mcp


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init()
    async with mcp.session_manager.run():
        yield


api = FastAPI(title="사내 메일 앱", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=(os.getenv("ALLOW_ORIGINS", "*").split(",")),
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReplyIn(BaseModel):
    body: str = ""


class ReminderIn(BaseModel):
    thread_key: str = ""
    only_overdue: bool = True
    note: str = ""


@api.get("/api/mails", summary="보낸 메일과 회신 현황")
def list_mails(thread_key: str = "", limit: int = 50) -> dict:
    return {
        "summary": store.thread_summary(thread_key),
        "mails": store.search(thread_key=thread_key, limit=limit),
    }


@api.get("/api/mails/{mail_id}", summary="메일 한 통 (본문 포함)")
def get_mail(mail_id: str) -> dict:
    mail = store.get(mail_id, with_body=True)
    return {"found": mail is not None, "mail": mail}


@api.post("/api/mails/{mail_id}/replied", summary="회신 온 것으로 표시")
def mark_replied(mail_id: str, payload: ReplyIn) -> dict:
    mail = store.mark_replied(mail_id, payload.body)
    return {"ok": mail is not None, "mail": mail}


@api.post("/api/reminders", summary="미회신자에게 리마인드 보내기")
def send_reminders(payload: ReminderIn) -> dict:
    # 오케스트레이터가 쓰는 것과 같은 기능을 화면에서도 씁니다(두 벌로 만들지 않습니다).
    return mcp_adapter.send_reminders(
        thread_key=payload.thread_key,
        only_overdue=payload.only_overdue,
        note=payload.note,
    )


@api.get("/api/connection", summary="메일 연결 상태 (가짜 메일함인지 사내 메일인지)")
def connection() -> dict:
    return get_adapter().describe()


@api.get("/api/health", summary="살아있나 확인")
def health() -> dict:
    return {"status": "ok", "app": "intra-mail", "adapter": get_adapter().name}


api.mount("/mcp", mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(api, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "9101")))
