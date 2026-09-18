"""데이터 모델.

핵심 개념 4가지
  App       : 앱스토어에 등록된 개발자 앱 (MCP 서버 한 대)
  AppTool   : 그 앱이 제공하는 기능 하나 (MCP tool). 등록 시 자동으로 읽어옵니다.
  AgentCard : 사용자가 "자주 쓰는 에이전트"로 만들어 둔 카드
  Run       : 사용자의 자연어 요청 1건과 그 처리 결과
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AppStatus(str, enum.Enum):
    active = "active"        # 앱스토어에 노출, 오케스트레이터가 호출 가능
    disabled = "disabled"    # 잠시 꺼둔 상태
    unreachable = "unreachable"  # 등록은 됐는데 최근 연결 실패


class AppVisibility(str, enum.Enum):
    """앱을 누가 쓸 수 있는지."""

    private = "private"    # 올린 사람만 사용 (개인용)
    pending = "pending"    # 공식 등록 신청 -> 관리자 승인 대기
    approved = "approved"  # 관리자 승인됨 -> 전원 사용 가능


class RunStatus(str, enum.Enum):
    queued = "queued"        # 큐에 들어감
    running = "running"      # 처리 중
    succeeded = "succeeded"
    failed = "failed"


class App(Base):
    """개발자가 MCP 규약대로 감싼 앱 1개. docs/WRAPPER_SPEC.md 참고."""

    __tablename__ = "apps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    # 오케스트레이터가 "이 앱을 언제 써야 하는지" 판단할 때 쓰는 한 문장
    usage_hint: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="etc")
    # 역할 태그. 같은 일을 하는 앱끼리 같은 값을 씁니다. 예) 사내규정검색
    # 오케스트레이터는 같은 태그의 앱 중 하나만 골라 씁니다(아래 규칙 참고).
    capability_tag: Mapped[str] = mapped_column(String(64), default="", index=True)
    # 유지보수 담당자를 찾기 위한 정보. 앱이 고장났을 때 누구에게 연락할지.
    owner: Mapped[str] = mapped_column(String(128), default="")  # 등록자 이름
    owner_user_id: Mapped[str] = mapped_column(String(128), default="", index=True)  # 사번
    owner_dept: Mapped[str] = mapped_column(String(128), default="")  # 소속
    owner_contact: Mapped[str] = mapped_column(String(256), default="")  # 메일/사내메신저
    icon: Mapped[str] = mapped_column(String(16), default="🧩")

    # 누가 쓸 수 있는 앱인지. 등록 직후에는 private 이고, 공식 등록을 신청하면
    # pending, 관리자가 승인하면 approved 가 됩니다.
    visibility: Mapped[AppVisibility] = mapped_column(
        Enum(AppVisibility, native_enum=False),
        default=AppVisibility.private,
        index=True,
    )

    # MCP streamable-HTTP 엔드포인트. 예) http://example-app:9001/mcp
    endpoint: Mapped[str] = mapped_column(String(512))
    # 사내 인증이 필요하면 헤더로 넣습니다. 예) {"Authorization": "Bearer ..."}
    auth_headers: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[AppStatus] = mapped_column(
        Enum(AppStatus, native_enum=False), default=AppStatus.active
    )
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    tools: Mapped[list["AppTool"]] = relationship(
        back_populates="app", cascade="all, delete-orphan", lazy="selectin"
    )


class AppTool(Base):
    """앱이 제공하는 기능 하나. 등록/새로고침 시 MCP tools/list 결과를 그대로 저장."""

    __tablename__ = "app_tools"
    __table_args__ = (UniqueConstraint("app_id", "name", name="uq_app_tool"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    app_id: Mapped[str] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)  # JSON Schema

    app: Mapped[App] = relationship(back_populates="tools")


class AgentCard(Base):
    """사용자가 개인 계정에 저장해 둔 '자주 쓰는 에이전트' 카드."""

    __tablename__ = "agent_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(16), default="⭐")
    # 이 카드를 누르면 채워지는 기본 요청문
    prompt_template: Mapped[str] = mapped_column(Text, default="")
    # 이 카드가 쓸 앱 목록(App.id). 비어 있으면 등록된 전체 앱을 후보로 씁니다.
    app_ids: Mapped[list] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)  # 카드 정렬 순서
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Run(Base):
    """자연어 요청 1건. 큐에 넣고 백그라운드에서 처리한 뒤 결과를 여기에 씁니다."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    card_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    request_text: Mapped[str] = mapped_column(Text)
    # 이 요청에서 후보로 쓸 앱 목록(App.id). 비어 있으면 등록된 전체 앱.
    app_ids: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False), default=RunStatus.queued, index=True
    )
    # 오케스트레이터가 세운 계획과 앱 호출 기록 (화면에서 진행상황 보여주는 용도)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    result_text: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppCallLog(Base):
    """앱이 실제로 불린 기록 1건.

    "이달의 앱"처럼 활용도를 집계해 시상하는 데 씁니다.
    호출할 때마다 한 줄씩 쌓이고, /api/stats/apps 에서 월별로 집계합니다.
    """

    __tablename__ = "app_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    app_id: Mapped[str] = mapped_column(String(36), index=True)
    # 앱이 지워져도 통계가 남도록 이름을 같이 복사해 둡니다.
    app_slug: Mapped[str] = mapped_column(String(64), default="")
    app_name: Mapped[str] = mapped_column(String(128), default="")
    owner_user_id: Mapped[str] = mapped_column(String(128), default="")

    tool_name: Mapped[str] = mapped_column(String(128), default="")
    user_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    run_id: Mapped[str] = mapped_column(String(36), default="")

    # 성공 = 앱이 에러 없이 결과를 돌려준 경우. 순위는 이 성공 호출 수로 매깁니다.
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_summary: Mapped[str] = mapped_column(String(500), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    # 월별 집계를 빠르고 단순하게 하려고 'YYYY-MM' 을 따로 저장합니다.
    period: Mapped[str] = mapped_column(String(7), index=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
