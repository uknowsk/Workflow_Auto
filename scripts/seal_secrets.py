"""이미 저장된 앱 접속 정보를 한 번에 잠급니다.

이 기능을 올리기 전에 등록된 앱들은 접속 정보가 DB 에 글자 그대로 들어 있습니다.
새로 저장할 때는 알아서 잠기지만, 예전 것은 이 스크립트로 한 번 정리합니다.

    docker compose exec backend python /srv/scripts/seal_secrets.py        # 무엇이 바뀔지만 보기
    docker compose exec backend python /srv/scripts/seal_secrets.py --apply # 실제로 잠그기

먼저 백업을 뜨고 돌리세요(scripts/backup.sh). 잠근 뒤 ENCRYPTION_KEY 를 바꾸면
접속 정보를 다시 입력해야 합니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

# app 패키지를 찾을 자리. 컨테이너 안(/srv)과 저장소 안(backend/) 둘 다 봅니다.
for _place in ("/srv", str(Path(__file__).resolve().parent.parent / "backend")):
    if _place not in sys.path:
        sys.path.insert(0, _place)

from app import crypto  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import App  # noqa: E402


def main(apply: bool) -> int:
    db = SessionLocal()
    try:
        apps = db.query(App).all()
        todo = [a for a in apps if a.auth_headers_sealed and not crypto.is_sealed(a.auth_headers_sealed)]

        print(f"등록된 앱 {len(apps)}개 중 아직 안 잠긴 접속 정보 {len(todo)}개")
        for app in todo:
            keys = ", ".join(sorted(app.auth_headers_sealed.keys()))
            print(f"  - {app.name} ({app.slug}): {keys}")

        if not todo:
            print("잠글 것이 없습니다.")
            return 0
        if not apply:
            print("\n실제로 잠그려면 --apply 를 붙여 다시 돌리세요.")
            return 0

        for app in todo:
            app.auth_headers = app.auth_headers_sealed  # setter 가 잠급니다
        db.commit()
        print(f"\n{len(todo)}개를 잠갔습니다.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
