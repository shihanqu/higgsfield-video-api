import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..repository.models.task import Task
from .delivery import send_results_to_client
from .task import (
    check_account_auth,
    check_task_status,
    process_i2v_tasks,
    update_account_balance,
)

TASK_TYPE_HANDLERS = {
    "i2v": {
        "handler": process_i2v_tasks,
    },
}

logger = logging.getLogger("higgsfield")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(process_queued_tasks, "interval", seconds=3, max_instances=1)
    scheduler.add_job(check_task_status, "interval", seconds=3, max_instances=1)
    scheduler.add_job(send_results_to_client, "interval", seconds=2, max_instances=1)
    scheduler.add_job(check_account_auth, "interval", seconds=60, max_instances=1)
    scheduler.add_job(update_account_balance, "interval", seconds=60, max_instances=1)
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
