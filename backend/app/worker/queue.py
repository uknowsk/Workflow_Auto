"""Redis 큐. 오래 걸리는 요청은 여기에 넣고 백그라운드에서 처리합니다.

100명이 동시에 버튼을 눌러도 웹 화면은 바로 응답하고, 실제 작업은
worker 컨테이너가 순서대로 처리합니다. 바쁘면 worker 수만 늘리면 됩니다.
"""
from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import get_settings

QUEUE_NAME = "workflow"


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


@lru_cache
def get_queue() -> Queue:
    # job_timeout: 한 요청이 이 시간을 넘기면 실패 처리
    return Queue(QUEUE_NAME, connection=get_redis(), default_timeout=1800)
