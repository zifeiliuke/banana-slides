import os
import logging
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


def is_rq_enabled() -> bool:
    backend = (os.getenv("TASK_QUEUE_BACKEND") or "").strip().lower()
    if backend == "rq" or backend == "redis":
        return True
    return bool((os.getenv("REDIS_URL") or "").strip())


def get_redis_url() -> str:
    return (os.getenv("REDIS_URL") or "redis://redis:6379/0").strip()


def _get_queue_names() -> tuple[str, str]:
    fast = (os.getenv("RQ_QUEUE_FAST") or "fast").strip()
    heavy = (os.getenv("RQ_QUEUE_HEAVY") or "heavy").strip()
    return fast, heavy


def enqueue_task(task_id: str, func_fqn: str, *, user_id: Optional[str], payload: dict[str, Any]) -> None:
    """
    Enqueue a background task into Redis/RQ.

    Args:
        task_id: DB task id (also used as rq job_id)
        func_fqn: fully qualified original function name (e.g. services.task_manager.generate_images_task)
        user_id: optional user id to build user-scoped AI service
        payload: JSON/pickle-serializable payload (only primitives / dict / list)
    """
    from redis import Redis
    from rq import Queue
    from services import rq_jobs

    fast_queue, heavy_queue = _get_queue_names()

    routes: dict[str, tuple[Callable[..., Any], str, int]] = {
        "services.task_manager.generate_descriptions_task": (rq_jobs.generate_descriptions_job, fast_queue, 60 * 60),
        "services.task_manager.generate_images_task": (rq_jobs.generate_images_job, heavy_queue, 60 * 60),
        "services.task_manager.generate_single_page_image_task": (rq_jobs.generate_single_page_image_job, heavy_queue, 60 * 60),
        "services.task_manager.edit_page_image_task": (rq_jobs.edit_page_image_job, heavy_queue, 60 * 60),
        "services.task_manager.generate_material_image_task": (rq_jobs.generate_material_image_job, heavy_queue, 60 * 30),
        "services.task_manager.export_editable_pptx_with_recursive_analysis_task": (
            rq_jobs.export_editable_pptx_recursive_job,
            heavy_queue,
            60 * 60 * 2,
        ),
    }

    if func_fqn not in routes:
        raise ValueError(f"Unsupported RQ task: {func_fqn}")

    job_func, queue_name, job_timeout = routes[func_fqn]

    redis_conn = Redis.from_url(get_redis_url())
    queue = Queue(queue_name, connection=redis_conn, default_timeout=job_timeout)

    logger.info(
        "Enqueuing task %s to rq queue=%s func=%s timeout=%ss",
        task_id,
        queue_name,
        func_fqn,
        job_timeout,
    )

    queue.enqueue(
        job_func,
        task_id=task_id,
        user_id=user_id,
        payload=payload,
        job_id=task_id,
        result_ttl=0,
        failure_ttl=60 * 60 * 24,
        job_timeout=job_timeout,
    )


def get_task_queue_info(task_id: str) -> Optional[dict[str, Any]]:
    """
    Get queue/position information for a task, if Redis/RQ is enabled and the job exists.
    """
    if not is_rq_enabled():
        return None

    try:
        from redis import Redis
        from rq import Queue
        from rq.job import Job

        redis_conn = Redis.from_url(get_redis_url())
        job = Job.fetch(task_id, connection=redis_conn)
        status = job.get_status(refresh=True)
        queue_name = getattr(job, "origin", None)

        info: dict[str, Any] = {
            "backend": "rq",
            "status": status,
            "queue": queue_name,
        }

        if queue_name:
            queue = Queue(queue_name, connection=redis_conn)
            if status == "queued":
                job_ids = list(queue.job_ids)
                info["queue_length"] = len(job_ids)
                try:
                    info["position"] = job_ids.index(task_id) + 1  # 1-based
                except ValueError:
                    info["position"] = None
            else:
                # best-effort: queue length for context; position no longer meaningful
                try:
                    info["queue_length"] = queue.count
                except Exception:
                    pass
                info["position"] = 0

        return info
    except Exception:
        return None
