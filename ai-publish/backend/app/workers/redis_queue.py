"""Redis 发布任务队列（替代进程内 BackgroundTasks）。"""

from __future__ import annotations

import threading

import redis
from loguru import logger

from app.config import get_settings

QUEUE_KEY = "ai-publish:task:execute"


class RedisTaskQueue:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: redis.Redis | None = None
        self._consumer_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.settings.redis_url, decode_responses=True)
        return self._client

    def ping(self) -> bool:
        try:
            return bool(self._get_client().ping())
        except Exception as exc:
            logger.warning("Redis 不可用: {}", exc)
            return False

    def enqueue_execute(self, task_id: int) -> None:
        if not self.settings.task_queue_enabled:
            self._run_inline(task_id)
            return
        try:
            self._get_client().rpush(QUEUE_KEY, str(task_id))
            logger.info("任务 #{} 已入队 {}", task_id, QUEUE_KEY)
        except Exception as exc:
            logger.warning("Redis 入队失败，改为进程内执行: {}", exc)
            self._run_inline(task_id)

    def _run_inline(self, task_id: int) -> None:
        from app.workers.task_runner import run_execute_task

        threading.Thread(target=run_execute_task, args=(task_id,), daemon=True).start()

    def dequeue_blocking(self, timeout: int = 5) -> int | None:
        item = self._get_client().blpop(QUEUE_KEY, timeout=timeout)
        if not item:
            return None
        return int(item[1])

    def consume_forever(self) -> None:
        from app.workers.task_runner import run_execute_task

        logger.info("Redis 任务消费者已启动，队列 {}", QUEUE_KEY)
        while not self._stop_event.is_set():
            try:
                task_id = self.dequeue_blocking(timeout=3)
                if task_id is None:
                    continue
                logger.info("消费者执行发布任务 #{}", task_id)
                run_execute_task(task_id)
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                logger.exception("消费者执行失败: {}", exc)

    def start_embedded_consumer(self) -> None:
        if not self.settings.task_queue_enabled or not self.settings.task_queue_embedded_consumer:
            return
        if self._consumer_thread and self._consumer_thread.is_alive():
            return
        if not self.ping():
            logger.warning("跳过内嵌 Redis 消费者：Redis 未连接")
            return
        self._stop_event.clear()
        self._consumer_thread = threading.Thread(target=self.consume_forever, daemon=True)
        self._consumer_thread.start()
        logger.info("内嵌 Redis 任务消费者线程已启动")

    def stop_embedded_consumer(self) -> None:
        self._stop_event.set()
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)
        self._consumer_thread = None


task_queue = RedisTaskQueue()
