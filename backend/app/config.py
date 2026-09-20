"""환경변수 한 곳에서 읽기. .env 파일이나 컨테이너 환경변수로 주입됩니다."""
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # populate_by_name: ADMIN_ID 처럼 별명을 붙인 값도 필드 이름으로 넣을 수 있게 합니다(테스트용).
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    # 저장소
    database_url: str = "postgresql+psycopg://workflow:workflow@localhost:5432/workflow"
    redis_url: str = "redis://localhost:6379/0"

    # 오케스트레이터 LLM (OpenAI 호환이면 무엇이든 꽂힙니다: Gauss, vLLM, Ollama ...)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "changeme"
    llm_model: str = "gauss"
    llm_tool_mode: str = "native"  # native | json
    llm_timeout: float = 120.0
    llm_max_steps: int = 8  # 한 번의 요청에서 앱을 최대 몇 번 호출할지

    # 등록된 앱(MCP 서버) 호출 타임아웃
    mcp_timeout: float = 60.0

    # --- 실행 환경 ---
    # dev  : 개발 PC. 편의 기능(헤더 로그인 등)을 켜 둘 수 있습니다.
    # production : 회사 서버. 위험한 설정이 하나라도 남아 있으면 서버가 뜨지 않습니다.
    #              (아래 production_problems() 참고)
    app_env: str = "dev"

    # 브라우저에서 이 백엔드를 부를 수 있는 주소. 쉼표로 여러 개.
    # "*" 는 아무 사이트나 허용한다는 뜻이라 운영에서는 쓸 수 없습니다.
    # 예) CORS_ORIGINS=http://workflow.samsung.net,http://10.1.2.3:3000
    cors_origins: str = "*"

    # --- 로그인 ---
    # 토큰 서명에 쓰는 비밀값. 회사에서는 반드시 긴 임의 문자열로 바꾸세요.
    secret_key: str = "change-me-in-production"
    # 출입증 유효시간. 짧을수록 안전합니다(로그아웃하거나 퇴사자 계정을 꺼도
    # 이미 받아 간 출입증은 이 시간만큼 살아 있습니다). 대신 일하는 도중에
    # 튕기면 안 되므로, 쓰고 있는 동안에는 /api/auth/refresh 로 연장됩니다.
    token_ttl_seconds: int = 60 * 60 * 2  # 2시간
    auth_backend: str = "password"  # password | sso (sso 는 아직 자리만)
    # 개발 편의: X-User-Id 헤더만으로 로그인한 척할 수 있게 합니다.
    # 회사 배포에서는 반드시 false 로 두세요.
    dev_header_auth: bool = True
    # 서버가 처음 뜰 때 만들 관리자 계정. .env 의 ADMIN_ID / ADMIN_PASSWORD 로 정합니다.
    # (예전 이름 BOOTSTRAP_ADMIN_ID / BOOTSTRAP_ADMIN_PASSWORD 도 그대로 읽힙니다)
    admin_id: str = Field(
        "", validation_alias=AliasChoices("ADMIN_ID", "BOOTSTRAP_ADMIN_ID")
    )
    admin_password: str = Field(
        "", validation_alias=AliasChoices("ADMIN_PASSWORD", "BOOTSTRAP_ADMIN_PASSWORD")
    )
    admin_name: str = "관리자"
    # 계정이 이미 있으면 비밀번호를 건드리지 않습니다. true 로 두면 기동할 때마다
    # .env 의 비밀번호로 덮어씁니다(비밀번호를 잊었을 때만 잠깐 켜세요).
    admin_reset_password: bool = False

    # --- 저장할 때 잠그는 열쇠 ---
    # 앱 접속 정보(토큰·비밀번호)를 DB 에 넣기 전에 이 열쇠로 잠급니다.
    # 비워 두면 SECRET_KEY 를 대신 씁니다. 따로 두면 로그인 열쇠(SECRET_KEY)를
    # 바꿔도 이미 저장해 둔 앱 접속 정보를 다시 입력하지 않아도 됩니다.
    encryption_key: str = ""

    # --- 파일 보관 위치 (앱 패키지, 양식) ---
    data_dir: str = "/srv/data"

    # --- 앱 생존 확인 ---
    healthcheck_interval_seconds: int = 300  # 5분마다. 0 이면 끔
    healthcheck_failure_threshold: int = 3   # 연속 3회 실패하면 등록자에게 알림

    # --- 예약(스케줄러) ---
    # 사내 표준시. 한국은 540분(UTC+9). "매일 09시"가 어느 나라 9시인지 정하는 값입니다.
    scheduler_tz_offset_minutes: int = 540
    # false 로 두면 예약을 아예 걸지 않습니다(예: 개발 PC).
    scheduler_enabled: bool = True
    # 예약은 이 간격보다 자주 돌 수 없습니다. 실수로 1분마다 도는 것을 막습니다.
    scheduler_min_interval_minutes: int = 5

    # --- 개인 대시보드 ---
    # 첫 화면에 어떤 칸을 띄울지 적은 파일. 비우면 기본값(config/dashboard.widgets.example.json
    # 과 같은 내용)을 씁니다. 사내 앱 이름이 다르면 이 파일만 바꿔 끼우세요.
    dashboard_widgets_file: str = ""
    # 대시보드가 앱 하나를 기다려 주는 시간. 느린 앱 때문에 첫 화면이 멈추면 안 됩니다.
    dashboard_timeout: float = 10.0

    # 서버가 뜰 때 자동 등록할 앱 목록 파일. 비우면 아무것도 등록하지 않습니다.
    # 예) SEED_FILE=config/apps.seed.json
    seed_file: str = ""

    # 관리자 사번 목록(쉼표 구분). 여기 있는 사람만 앱을 '공식 승인' 할 수 있습니다.
    # 예) ADMIN_USER_IDS=E1001,E2001
    admin_user_ids: str = ""

    # 사내 SSO 로 들어왔을 때 관리자로 볼 아이디 목록(쉼표 구분).
    # 예) ADMIN_SSO_IDS=sk1980.kim
    admin_sso_ids: str = ""

    # 개발 편의: 서버 시작 시 테이블 자동 생성
    auto_create_tables: bool = True

    @property
    def admins(self) -> set[str]:
        return {x.strip() for x in self.admin_user_ids.split(",") if x.strip()}

    @property
    def admin_sso(self) -> set[str]:
        """SSO 아이디는 대소문자를 가리지 않습니다(SK1980.Kim 도 같은 사람)."""
        return {x.strip().lower() for x in self.admin_sso_ids.split(",") if x.strip()}


    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def crypto_key(self) -> str:
        """저장할 때 잠그는 열쇠. 따로 안 정했으면 로그인 열쇠를 같이 씁니다."""
        return self.encryption_key or self.secret_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


# 아무도 안 바꾸고 그대로 배포하면 위험한 기본값들
DEFAULT_SECRET_KEY = "change-me-in-production"
MIN_SECRET_KEY_LENGTH = 32


def production_problems(settings: Settings) -> list[str]:
    """운영(APP_ENV=production)에서 그대로 두면 안 되는 설정을 모두 찾습니다.

    한 번에 전부 돌려줍니다. 하나 고치고 다시 띄웠더니 또 다른 게 걸리는 일을
    막으려는 것입니다. 개발 환경(APP_ENV=dev)에서는 빈 목록입니다.
    """
    if not settings.is_production:
        return []

    problems: list[str] = []

    if settings.dev_header_auth:
        problems.append(
            "DEV_HEADER_AUTH=true 입니다. 이대로면 X-User-Id 헤더에 사번만 적어도 "
            "그 사람으로 로그인됩니다. .env 에 DEV_HEADER_AUTH=false 를 넣으세요."
        )

    if settings.secret_key == DEFAULT_SECRET_KEY:
        problems.append(
            "SECRET_KEY 가 예시값 그대로입니다. 이 값을 아는 사람은 아무 계정의 "
            "출입증이든 위조할 수 있습니다. "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\" 로 만든 값을 넣으세요."
        )
    elif len(settings.secret_key) < MIN_SECRET_KEY_LENGTH:
        problems.append(
            f"SECRET_KEY 가 너무 짧습니다({len(settings.secret_key)}자). "
            f"{MIN_SECRET_KEY_LENGTH}자 이상으로 넣으세요."
        )

    if "*" in settings.cors_origin_list:
        problems.append(
            "CORS_ORIGINS 가 * 입니다. 사내 어느 페이지에서든 이 서버를 부를 수 있게 "
            "됩니다. CORS_ORIGINS 에 실제 접속 주소만 쉼표로 적으세요. "
            "예) CORS_ORIGINS=http://workflow.samsung.net"
        )

    if not settings.cors_origin_list:
        problems.append(
            "CORS_ORIGINS 가 비어 있습니다. 브라우저에서 화면이 서버를 못 부릅니다. "
            "접속 주소를 적으세요."
        )

    return problems


class UnsafeProductionSettings(RuntimeError):
    """운영에 올리면 안 되는 설정이 남아 있을 때. 서버를 일부러 못 뜨게 합니다."""


def check_production_safety(settings: Settings | None = None) -> None:
    """서버가 뜨기 전에 부릅니다. 문제가 있으면 이유를 적어 두고 멈춥니다.

    경고만 찍으면 아무도 안 보고 그대로 운영에 올라가기 때문에, 아예 안 뜨게 합니다.
    개발 PC 는 APP_ENV 를 건드리지 않으면(기본 dev) 아무 영향이 없습니다.
    """
    found = production_problems(settings or get_settings())
    if not found:
        return
    lines = "\n".join(f"  {i}. {p}" for i, p in enumerate(found, 1))
    raise UnsafeProductionSettings(
        "\n\n[서버를 띄우지 않았습니다] APP_ENV=production 인데 위험한 설정이 "
        f"{len(found)}개 남아 있습니다.\n{lines}\n\n"
        ".env 를 고치고 다시 띄우세요. 개발 PC 라면 APP_ENV 를 지우거나 dev 로 두세요.\n"
    )
