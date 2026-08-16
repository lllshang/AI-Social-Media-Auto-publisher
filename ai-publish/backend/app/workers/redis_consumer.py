"""独立 Redis 任务消费者进程（Docker worker 服务入口）。"""

from app.workers.redis_queue import task_queue


def main() -> None:
    task_queue.consume_forever()


if __name__ == "__main__":
    main()
