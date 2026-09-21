"""관리자가 화면에서 바꾸는 값들.

`.env` 는 서버를 다시 띄워야 바뀌지만, 여기 값들은 관리자가 화면에서 고치면
바로 적용됩니다. 기록을 며칠 보관할지, Gauss 를 얼마나 쓸 수 있는지처럼
"운영하면서 조절하는 숫자"가 여기 들어갑니다.

값은 전부 숫자이고, 표(admin_settings)에 한 줄씩 저장합니다.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AdminSetting


@dataclass(frozen=True)
class Knob:
    """관리자가 만질 수 있는 값 하나."""

    key: str
    label: str        # 화면에 보일 이름
    hint: str         # 화면에 보일 설명
    default: int
    minimum: int = 0
    maximum: int = 10_000_000


KNOBS: tuple[Knob, ...] = (
    Knob(
        key="run_retention_days",
        label="실행 이력 보관 기간(일)",
        hint="요청문과 결과물이 남는 기간입니다. 0 이면 지우지 않습니다.",
        default=90,
        maximum=3650,
    ),
    Knob(
        key="audit_retention_days",
        label="감사 기록 보관 기간(일)",
        hint="누가 언제 무엇을 했는지의 기록입니다. 0 이면 지우지 않습니다.",
        default=365,
        maximum=3650,
    ),
    Knob(
        key="llm_monthly_token_limit",
        label="1인당 월 Gauss 토큰 한도",
        hint="한 사람이 한 달에 쓸 수 있는 양입니다. 0 이면 제한 없음(기본).",
        default=0,
    ),
)

BY_KEY = {knob.key: knob for knob in KNOBS}


def get(db: Session, key: str) -> int:
    """지금 값. 아직 정한 적 없으면 기본값."""
    knob = BY_KEY[key]
    row = db.get(AdminSetting, key)
    if row is None:
        return knob.default
    try:
        return int(row.value)
    except (TypeError, ValueError):
        # 값이 깨져 있어도 서버가 멈추면 안 됩니다. 기본값으로 계속 갑니다.
        return knob.default


def set_value(db: Session, key: str, value: int) -> int:
    """값을 바꿉니다. 범위를 벗어나면 범위 안으로 당겨 넣습니다."""
    knob = BY_KEY[key]
    value = max(knob.minimum, min(knob.maximum, int(value)))
    row = db.get(AdminSetting, key)
    if row is None:
        db.add(AdminSetting(key=key, value=str(value)))
    else:
        row.value = str(value)
    db.commit()
    return value


def all_values(db: Session) -> list[dict]:
    """화면에 뿌릴 모양으로 전부."""
    return [
        {
            "key": knob.key,
            "label": knob.label,
            "hint": knob.hint,
            "value": get(db, knob.key),
            "default": knob.default,
        }
        for knob in KNOBS
    ]
