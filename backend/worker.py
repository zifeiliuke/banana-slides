import logging
import os


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0").strip()
    queues = [q.strip() for q in (os.getenv("RQ_QUEUES", "fast,heavy").split(",")) if q.strip()]

    from redis import Redis
    from rq import Queue, Worker

    redis_conn = Redis.from_url(redis_url)
    queue_objs = [Queue(name, connection=redis_conn) for name in queues]

    logging.getLogger(__name__).info("Starting RQ worker redis=%s queues=%s", redis_url, queues)

    worker = Worker(queue_objs, connection=redis_conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
