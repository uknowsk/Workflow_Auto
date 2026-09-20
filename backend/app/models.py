"""데이터 모델.

핵심 개념
  User        : 사번으로 로그인하는 사용자
  App         : 앱스토어에 등록된 개발자 앱 (MCP 서버 한 대)
  AppTool     : 그 앱이 제공하는 기능 하나 (MCP tool). 등록 시 자동으로 읽어옵니다.
  AgentCard   : 사용자가 "자주 쓰는 에이전트"로 만들어 둔 카드
  Run         : 사용자의 자연어 요청 1건과 그 처리 결과
  FormTemplate: 결과를 채워 넣을 양식(엑셀/문서 틀). 중앙 서버에 보관합니다.
  Launcher    : 개인 PC에 설치해 서버 요청을 대신 실행하는 작은 연결 프로그램
  AuditLog    : 누가 언제 무엇을 했는지 남기는 감사 기록
  LlmUsage    : Gauss 토큰 사용량
  Recipe      : 한 번 잘 돌아간 앱 호출 흐름에 이름을 붙여 저장한 것(워크플로우)
  Schedule    : 시간이 되면 스스로 실행되는 예약
  AppFeedback : 앱을 써 본 사람이 등록자에게 남긴 의견(VOC)
  AppVersion  : 앱을 새 버전으로 올린 이력 (되돌리기용)
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


class RuntimeLocation(str, enum.Enum):
    """이 앱이 어디서 도나."""

    server = "server"  # 중앙 서버에서 구동 (기본)
    pc = "pc"          # 개인 PC에 설치해 구동. Launcher 가 대신 실행합니다.


class SourceType(str, enum.Enum):
    """앱 소스를 어떻게 받았나."""

    manual = "manual"  # 이미 돌고 있는 어댑터 주소만 등록
    github = "github"  # GitHub 주소로 등록
    zip = "zip"        # ZIP 파일 업로드


class AppVisibility(str, enum.Enum):
    """앱을 누가 쓸 수 있는지."""

    private = "private"    # 올린 사람만 사용 (개인용)
    pending = "pending"    # 공식 등록 신청 -> 관리자 승인 대기
    approved = "approved"  # 관리자 승인됨 -> 전원 사용 가능


class RunStatus(str, enum.Enum):
    queued = "queued"                      # 큐에 들어감
    planning = "planning"                  # 어떤 앱을 쓸지 계획을 세우는 중
    awaiting_approval = "awaiting_approval"  # 되돌릴 수 없는 앱이 껴 있어 사용자 확인 대기
    running = "running"                    # 처리 중
    succeeded = "succeeded"
    failed = "failed"
    rejected = "rejected"                  # 사용자가 계획을 거부함


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
    # 서버 구동형은 서버가 앱을 띄운 뒤 이 값을 채웁니다.
    endpoint: Mapped[str] = mapped_column(String(512), default="")

    # --- 어디서 도는 앱인가 ---
    runtime_location: Mapped[RuntimeLocation] = mapped_column(
        Enum(RuntimeLocation, native_enum=False), default=RuntimeLocation.server
    )
    # PC 구동형일 때 이 앱을 실행해 줄 Launcher
    launcher_id: Mapped[str] = mapped_column(String(36), default="", index=True)

    # --- 소스를 어떻게 받았나 ---
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, native_enum=False), default=SourceType.manual
    )
    source_url: Mapped[str] = mapped_column(String(512), default="")  # GitHub 주소
    package_path: Mapped[str] = mapped_column(String(512), default="")  # 풀어 둔 폴더
    package_version: Mapped[str] = mapped_column(String(64), default="")

    # 되돌릴 수 없는 일(메일 발송, 결재 상신 등)을 하는 앱이면 True.
    # 이런 앱이 계획에 끼면 오케스트레이터가 실행 전에 사용자에게 확인을 받습니다.
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    # 사내 인증이 필요하면 헤더로 넣습니다. 예) {"Authorization": "Bearer ..."}
    auth_headers: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[AppStatus] = mapped_column(
        Enum(AppStatus, native_enum=False), default=AppStatus.active
    )
    last_error: Mapped[str] = mapped_column(Text, default="")
    # 마지막으로 "살아있니?" 확인에 성공한 시각
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
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
    # 레시피 카드. 값이 있으면 이 카드는 요청문 대신 저장된 레시피를 재실행합니다.
    recipe_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
    # 레시피로 실행했으면 그 레시피 id. 자연어 요청이면 비어 있습니다.
    recipe_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 예약이 스스로 실행한 것이면 그 예약 id. 사람이 눌렀으면 비어 있습니다.
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 레시피 실행에 넣은 값들. 예) {"회의록": "..."} (확인 대기 중에도 남아 있어야 합니다)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    request_text: Mapped[str] = mapped_column(Text)
    # 이 요청에서 후보로 쓸 앱 목록(App.id). 비어 있으면 등록된 전체 앱.
    app_ids: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False), default=RunStatus.queued, index=True
    )
    # 실행 전에 세운 계획. 확인이 필요한 앱이 끼면 사용자에게 보여 주고 승인을 받습니다.
    plan: Mapped[list] = mapped_column(JSON, default=list)
    plan_summary: Mapped[str] = mapped_column(Text, default="")
    needs_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str] = mapped_column(String(128), default="")

    # 결과를 채워 넣을 양식(FormTemplate.id). 비우면 자유 형식.
    form_id: Mapped[str] = mapped_column(String(36), default="")

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


class User(Base):
    """사용자. 지금은 사번 + 비밀번호로 로그인합니다.

    나중에 사내 SSO 를 붙이면 이 표는 "프로필 저장소" 역할만 하게 됩니다.
    비밀번호는 원문을 저장하지 않고 해시만 저장합니다.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)  # 사번
    name: Mapped[str] = mapped_column(String(128), default="")
    dept: Mapped[str] = mapped_column(String(128), default="")
    contact: Mapped[str] = mapped_column(String(256), default="")

    password_hash: Mapped[str] = mapped_column(String(256), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # 화면 테마. 개인 계정에 저장해서 어느 PC 에서 들어와도 같은 모양으로 보입니다.
    # 값은 frontend/lib/theme.ts 의 THEMES 와 같아야 합니다.
    theme: Mapped[str] = mapped_column(String(32), default="white")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Launcher(Base):
    """Launcher - 개인 PC에 설치하는 작은 연결 프로그램.

    서버는 남의 PC에 깔린 앱을 직접 실행할 수 없습니다. 그래서 PC 쪽에서
    서버로 "일 있나요?" 하고 물어보러 오는 방식을 씁니다(아웃바운드만 쓰므로
    보안 환경에서도 방화벽을 열 필요가 없습니다).

    앱스토어의 앱을 내 PC에 설치하는 일도 Launcher 가 맡습니다.
    뼈대에서는 등록과 작업 주고받기 자리까지만 만들어 두었습니다.
    실제 Launcher 프로그램은 다음 단계입니다.
    """

    __tablename__ = "launchers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)  # 이 PC 주인
    hostname: Mapped[str] = mapped_column(String(256), default="")
    token_hash: Mapped[str] = mapped_column(String(256), default="")
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LauncherJob(Base):
    """Launcher 가 가져가 실행할 작업 1건."""

    __tablename__ = "launcher_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    launcher_id: Mapped[str] = mapped_column(String(36), index=True)
    app_id: Mapped[str] = mapped_column(String(36), default="")
    tool_name: Mapped[str] = mapped_column(String(128), default="")
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FormTemplate(Base):
    """결과물을 채워 넣을 양식. 중앙 서버에 파일로 보관합니다.

    예) 주간보고 양식.xlsx, 출장보고서.docx, 회의록 틀.md
    """

    __tablename__ = "form_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="etc")

    filename: Mapped[str] = mapped_column(String(256), default="")
    content_type: Mapped[str] = mapped_column(String(128), default="")
    stored_path: Mapped[str] = mapped_column(String(512), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    # 텍스트 양식(.md/.txt)이면 본문을 그대로 담아 둡니다.
    # 오케스트레이터가 이 틀에 맞춰 결과를 작성할 때 씁니다.
    text_body: Mapped[str] = mapped_column(Text, default="")

    uploaded_by: Mapped[str] = mapped_column(String(128), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """감사 기록: 누가, 언제, 무엇을 했는지.

    사내 보안 요건상 거의 확실히 요구됩니다. 로그인, 앱 등록/승인, 요청 실행,
    앱 호출, 양식 다운로드처럼 사람이 한 행동을 남깁니다.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor: Mapped[str] = mapped_column(String(128), index=True, default="")  # 사번
    action: Mapped[str] = mapped_column(String(64), index=True, default="")
    target_type: Mapped[str] = mapped_column(String(32), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    # 요청문 요약, 앱 이름, 넘긴 인자 요약 등. 원문 전체는 담지 않습니다.
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class LlmUsage(Base):
    """Gauss 토큰 사용량 1건. 청구서 보고 놀라지 않으려고 남깁니다."""

    __tablename__ = "llm_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    run_id: Mapped[str] = mapped_column(String(36), default="")
    model: Mapped[str] = mapped_column(String(128), default="")

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    period: Mapped[str] = mapped_column(String(7), index=True, default="")  # YYYY-MM
    day: Mapped[str] = mapped_column(String(10), index=True, default="")    # YYYY-MM-DD
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    """등록자에게 보내는 알림. 뼈대에서는 기록만 남기고 화면에서 보여 줍니다.

    예) "내 앱이 3회 연속 응답하지 않습니다"
    """

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    kind: Mapped[str] = mapped_column(String(32), default="info")
    title: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Recipe(Base):
    """워크플로우 레시피 - 한 번 잘 돌아간 앱 호출 흐름에 이름을 붙여 저장한 것.

    카드가 앱 하나라면, 레시피는 '앱 여러 개를 엮은 카드'입니다.
    예) 회의록 정리 -> 할 일 추출 -> 담당자에게 메일

    steps 한 칸의 모양
      {"app_id": "...", "app_slug": "...", "app_name": "회의록 정리",
       "tool": "summarize", "arguments": {...}, "title": "회의록 요약"}

    arguments 안에는 {{변수}} 를 넣을 수 있습니다.
      {{회의록}}  실행할 때 사용자가 채워 넣는 값
      {{step1}}   1번째 단계가 돌려준 결과
      {{today}}   오늘 날짜(YYYY-MM-DD)
    """

    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(16), default="🧾")

    steps: Mapped[list] = mapped_column(JSON, default=list)
    # 단계 결과를 모아 최종 결과물을 쓰게 하는 지시문.
    # 비우면 단계 결과를 그대로 이어 붙입니다(LLM 을 부르지 않아 빠릅니다).
    final_instruction: Mapped[str] = mapped_column(Text, default="")
    # 결과를 채워 넣을 양식(FormTemplate.id). 비우면 자유 형식.
    form_id: Mapped[str] = mapped_column(String(36), default="")
    # 어떤 실행 기록에서 뽑아 왔는지 (되짚어 볼 때 씁니다)
    source_run_id: Mapped[str] = mapped_column(String(36), default="")

    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ScheduleTrigger(str, enum.Enum):
    """언제 돌릴지."""

    once = "once"          # 지정한 시각에 딱 한 번 (예: 회신기한 하루 전)
    daily = "daily"        # 매일(또는 지정한 요일) 정해진 시각에
    interval = "interval"  # N분마다 반복


class ScheduleAction(str, enum.Enum):
    """무엇을 돌릴지."""

    request = "request"  # 자연어 요청을 오케스트레이터에 맡김
    recipe = "recipe"    # 저장해 둔 레시피를 그대로 재실행
    tool = "tool"        # 특정 앱의 기능 하나만 바로 호출


class Schedule(Base):
    """예약 - 시간이 되면 스스로 움직이는 부분.

    회신기한 리마인드나 수명업무 기한 알림이 전부 이 위에서 돕니다.
    "기한 하루 전"은 run_at 에 기한을, lead_minutes 에 1440(=24시간)을 넣으면 됩니다.
    """

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # ── 언제 ───────────────────────────────────────────────────────
    trigger: Mapped[ScheduleTrigger] = mapped_column(
        Enum(ScheduleTrigger, native_enum=False), default=ScheduleTrigger.once
    )
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    at_time: Mapped[str] = mapped_column(String(5), default="")  # daily 용. "09:00"
    # daily 에서 특정 요일만 돌리고 싶을 때. 0=월 ... 6=일. 비우면 매일.
    weekdays: Mapped[list] = mapped_column(JSON, default=list)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # run_at 보다 이만큼 '미리' 실행합니다. 1440 이면 기한 하루 전.
    lead_minutes: Mapped[int] = mapped_column(Integer, default=0)

    # ── 무엇을 ─────────────────────────────────────────────────────
    action: Mapped[ScheduleAction] = mapped_column(
        Enum(ScheduleAction, native_enum=False), default=ScheduleAction.request
    )
    request_text: Mapped[str] = mapped_column(Text, default="")   # action=request
    app_ids: Mapped[list] = mapped_column(JSON, default=list)     # action=request
    recipe_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # action=recipe
    variables: Mapped[dict] = mapped_column(JSON, default=dict)   # action=recipe
    app_id: Mapped[str] = mapped_column(String(36), default="")   # action=tool
    tool_name: Mapped[str] = mapped_column(String(128), default="")  # action=tool
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)   # action=tool

    # 되돌릴 수 없는 앱(메일 발송 등)이 껴 있는 예약은, 만들 때 한 번 확인을 받습니다.
    # 예약이 실행될 때는 사람이 화면 앞에 없으므로 그때 물어볼 수가 없기 때문입니다.
    pre_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── 예약 상태 (화면에 보여주는 값) ─────────────────────────────
    job_id: Mapped[str] = mapped_column(String(64), default="")  # Redis 큐의 예약 번호
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[str] = mapped_column(String(36), default="")
    last_status: Mapped[str] = mapped_column(String(24), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    run_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ToolNote(Base):
    """도구 서랍의 간단 메모 한 장. 개인 계정에 저장됩니다."""

    __tablename__ = "tool_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Drawing(Base):
    """그리기 도구로 그린 그림 한 장.

    그림은 PNG 를 data URL 문자열로 통째로 저장합니다. 파일 서버를 따로 두지
    않아도 되고 폐쇄망에서 백업이 DB 하나로 끝나기 때문입니다. 대신 한 장이
    커질 수 있어 API 에서 크기를 제한합니다(MAX_DRAWING_BYTES).
    """

    __tablename__ = "drawings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    # data:image/png;base64,... 모양의 문자열
    image: Mapped[str] = mapped_column(Text, default="")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class VocKind(str, enum.Enum):
    """의견의 종류. 고르는 값이 많으면 아무도 안 고르므로 셋만 둡니다."""

    bug = "bug"            # 잘 안 돼요
    idea = "idea"          # 이런 게 있으면 좋겠어요
    question = "question"  # 사용법을 모르겠어요


class VocStatus(str, enum.Enum):
    """등록자가 옮겨 놓는 처리 상태."""

    open = "open"                # 접수됨(아직 안 봤거나 검토 전)
    in_progress = "in_progress"  # 고치는 중
    done = "done"                # 처리 완료
    wontfix = "wontfix"          # 안 고치기로 함(이유를 답변에 적습니다)


class AppFeedback(Base):
    """앱스토어 앱에 사용자가 남긴 의견(VOC) 한 건.

    "누가 - 어떤 앱에 - 무엇을" 이 한 줄에 다 있어야 등록자가 바로 고칠 수
    있습니다. 그래서 의견을 남긴 시점의 앱 버전(app_version)까지 같이 적어
    둡니다. 고쳐 놓은 버전에 대한 옛날 제보를 붙잡고 있지 않기 위해서입니다.
    """

    __tablename__ = "app_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    app_id: Mapped[str] = mapped_column(String(36), index=True)
    # 앱이 지워져도 의견 기록은 남도록 이름을 복사해 둡니다(감사 기록과 같은 이유).
    app_name: Mapped[str] = mapped_column(String(128), default="")
    # 받는 사람 = 앱을 올린 사람. 앱의 주인이 바뀌면 이 값도 같이 바꿔 줍니다.
    owner_user_id: Mapped[str] = mapped_column(String(128), default="", index=True)

    user_id: Mapped[str] = mapped_column(String(128), index=True)  # 의견 쓴 사람(사번)
    user_name: Mapped[str] = mapped_column(String(128), default="")

    kind: Mapped[VocKind] = mapped_column(
        Enum(VocKind, native_enum=False), default=VocKind.bug, index=True
    )
    # 별점. 0 이면 "안 매김". 별점만으로는 뭘 고칠지 모르므로 어디까지나 덤입니다.
    rating: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    # 의견을 남길 때 돌고 있던 앱 버전. 고친 뒤에 들어온 제보인지 구분합니다.
    app_version: Mapped[str] = mapped_column(String(64), default="")
    # 어떤 실행에서 겪은 일인지(있으면). 등록자가 그 실행 기록을 찾아볼 수 있습니다.
    run_id: Mapped[str] = mapped_column(String(36), default="")

    status: Mapped[VocStatus] = mapped_column(
        Enum(VocStatus, native_enum=False), default=VocStatus.open, index=True
    )
    reply: Mapped[str] = mapped_column(Text, default="")  # 등록자 답변
    replied_by: Mapped[str] = mapped_column(String(128), default="")
    replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class AppVersion(Base):
    """앱을 새 버전으로 올린 기록 한 줄.

    업데이트는 바로 반영됩니다(매번 재승인을 받게 하면 아무도 업데이트를 안
    합니다). 대신 여기에 이력이 남고, 공식 앱이면 관리자에게 알림이 가며,
    문제가 있으면 이전 버전으로 되돌릴 수 있습니다.

    GitHub/ZIP 으로 올린 앱은 버전마다 폴더를 따로 두기 때문에(packages.py)
    package_path 만 다시 가리키면 진짜로 되돌아갑니다.
    """

    __tablename__ = "app_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    app_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")  # 무엇이 바뀌었는지

    # 이 버전이 쓰던 값들. 되돌리기는 이 값들을 앱에 다시 써 넣는 일입니다.
    endpoint: Mapped[str] = mapped_column(String(512), default="")
    source_type: Mapped[str] = mapped_column(String(16), default="manual")
    source_url: Mapped[str] = mapped_column(String(512), default="")
    source_ref: Mapped[str] = mapped_column(String(128), default="")  # 브랜치/태그
    package_path: Mapped[str] = mapped_column(String(512), default="")
    tool_count: Mapped[int] = mapped_column(Integer, default=0)

    # 지금 돌고 있는 버전이면 True. 되돌리면 이 표시가 옮겨 갑니다.
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # 되돌리기로 만들어진 줄이면, 어느 버전으로 되돌린 것인지.
    rolled_back_from: Mapped[str] = mapped_column(String(36), default="")

    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
