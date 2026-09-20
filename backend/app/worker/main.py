"""worker 컨테이너 진입점:  python -m app.worker.main"""
from rq import Worker

from app.config import check_production_safety
from app.worker.queue import QUEUE_NAME, get_redis


def main() -> None:
    # 백엔드와 같은 .env 를 쓰므로 여기서도 똑같이 막습니다.
    check_production_safety()
    Worker([QUEUE_NAME], connection=get_redis()).work(with_scheduler=True)


if __name__ == "__main__":
    main()
