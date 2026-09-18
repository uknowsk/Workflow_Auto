"""SQLAlchemy 엔진/세션. 동기 방식이라 읽기 쉽고 디버깅이 쉽습니다."""
from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI 의존성. 요청 하나당 세션 하나."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 나중에 덧붙인 칼럼들. create_all() 은 "없는 테이블"만 만들 뿐 이미 있는
# 테이블에 칼럼을 더하지는 못해서, 아래 목록을 보고 빠진 것만 채워 넣습니다.
# 사내 정식 배포에서는 alembic 으로 관리하세요.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "runs": {"recipe_id": "VARCHAR(36)", "schedule_id": "VARCHAR(36)", "variables": "JSON"},
    "agent_cards": {"recipe_id": "VARCHAR(36)"},
    "users": {"theme": "VARCHAR(32) DEFAULT 'white'"},
}


def add_missing_columns() -> None:
    inspector = inspect(engine)
    for table, columns in _ADDED_COLUMNS.items():
        if not inspector.has_table(table):
            continue  # 새로 만들어지는 테이블이면 create_all() 이 이미 넣어 줍니다
        existing = {c["name"] for c in inspector.get_columns(table)}
        missing = {n: ddl for n, ddl in columns.items() if n not in existing}
        if not missing:
            continue
        with engine.begin() as conn:
            for name, ddl in missing.items():
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def create_all() -> None:
    from app import models  # noqa: F401  테이블 등록을 위해 import

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
