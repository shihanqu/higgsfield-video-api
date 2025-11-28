import asyncio
import logging
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Add parent directories to path for config import
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from config import (
    RESULT_DELIVERY_INTERVAL,
    TASK_QUEUE_POLL_INTERVAL,
    TASK_STATUS_MAX_INSTANCES,
    TASK_STATUS_POLL_INTERVAL,
)

from ..repository.models.task import Task
from .delivery import send_results_to_client
from .task import (
    check_task_status,
    process_i2v_tasks,
    process_soul_tasks,
    process_t2i_tasks,
    update_account_balance,
)

TASK_TYPE_HANDLERS = {
    "i2v": {
        "handler": process_i2v_tasks,
    },
    "t2i": {
        "handler": process_t2i_tasks,
    },
    "soul": {
        "handler": process_soul_tasks,
    },
}

logger = logging.getLogger("higgsfield")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        process_queued_tasks,
        "interval",
        seconds=TASK_QUEUE_POLL_INTERVAL,
        max_instances=1,
    )
    scheduler.add_job(
        check_task_status,
        "interval",
        seconds=TASK_STATUS_POLL_INTERVAL,
        max_instances=TASK_STATUS_MAX_INSTANCES,
    )
    scheduler.add_job(
        send_results_to_client,
        "interval",
        seconds=RESULT_DELIVERY_INTERVAL,
        max_instances=1,
    )
    # Update account balance every 10 minutes (not critical, just for display)
    scheduler.add_job(update_account_balance, "interval", minutes=10, max_instances=1)
    # Note: Auth refresh removed - use 'python scripts/manage_accounts.py login --force' if session expires
    scheduler.start()


async def process_queued_tasks():
    """
    Process pending tasks from the database.

    This function runs every 3 seconds and processes all pending tasks.
    """
    pending_tasks = await Task.filter(status="pending").order_by("id")

    if not pending_tasks:
        return

    logger.info(f"***   Received {len(pending_tasks)} Pending Tasks   ***")

    for task in pending_tasks:
        if task.type in TASK_TYPE_HANDLERS:
            try:
                task.status = "starting"
                task.update_datetime()
                await task.save()

                asyncio.create_task(TASK_TYPE_HANDLERS[task.type]["handler"](task))
                logger.info(f"***   Task {task.task_id} Started Processing   ***")
            except Exception as e:
                task.status = "failed"
                task.result.append(str(e))
                task.update_datetime()
                await task.save()
                logger.error(f"***   Task {task.task_id} Failed: {str(e)}   ***")
        else:
            task.status = "failed"
            task.result.append(f"Unknown task type: {task.type}")
            task.update_datetime()
            await task.save()
            logger.error(
                f"***   Task {task.task_id} Failed: Unknown task type {task.type}   ***"
            )
