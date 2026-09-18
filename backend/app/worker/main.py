"""worker 컨테이너 진입점:  python -m app.worker.main"""
from rq import Worker

from app.worker.queue import QUEUE_NAME, get_redis


def main() -> None:
    Worker([QUEUE_NAME], connection=get_redis()).work(with_scheduler=True)


if __name__ == "__main__":
    main()
