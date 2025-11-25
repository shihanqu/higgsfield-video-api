import logging
from datetime import datetime, timedelta, timezone

from ..repository.models.account import HiggsfieldAccount
from ..repository.models.task import Task
from ..services.higgsfield import (
    generate_video,
    get_account_info,
    get_job_set_id,
    get_last_used_account,
    refresh_account_auth,
)

logger = logging.getLogger("higgsfield")


async def process_i2v_tasks(task: Task):
    prompt = task.parameters_json.get("prompt", "")
    image_path = task.parameters_json.get("image_path")
    motion = task.parameters_json.get("motion")
    model = task.parameters_json.get("model")
    duration = task.parameters_json.get("duration")

    try:
        account = await get_last_used_account()
        if not account:
            logger.error("No active account found")
            task.status = "failed"
            task.message = "No active account found"
            await task.save()
            return
        task.account = account
        await task.save()  # Save account assignment
        job_set = await generate_video(
            prompt, image_path, motion, model, duration, account
        )
    except Exception as e:
        logger.error(f"Error generating video: {e}")
        task.status = "failed"
        task.message = str(e)
        await task.save()
        return
    try:
        job_id = job_set["job_sets"][0]["id"]
        task.status = "processing"
        task.api_task_id = job_id
        await task.save()
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        task.status = "failed"
        task.message = str(e)
        await task.save()
        return


async def check_task_status():
    tasks = await Task.filter(status="processing")
    for task in tasks:
        try:
            account = await task.account
            job_set = await get_job_set_id(task.api_task_id, account)
            if job_set["jobs"][0]["status"] == "completed":
                task.status = "success"
                task.result = [job_set["jobs"][0]["result"]["url"]]
                await task.save()
            elif job_set["jobs"][0]["status"] == "failed":
                task.status = "failed"
                task.message = job_set["jobs"][0]["error"]
                await task.save()
        except Exception as e:
            logger.error(f"Error getting job set for task {task.task_id}: {e}")
            continue  # Continue with other tasks instead of returning


async def check_account_auth():
    accounts = await HiggsfieldAccount.all()
    for account in accounts:
        try:
            if account.last_updated_at and account.last_updated_at < datetime.now(
                timezone.utc
            ) - timedelta(days=1):
                await refresh_account_auth(account)
                logger.info(f"Refreshed account auth for {account.id}")
        except Exception as e:
            logger.error(f"Error refreshing account auth: {e}")


async def update_account_balance():
    accounts = await HiggsfieldAccount.filter(is_active=True)
    for account in accounts:
        try:
            response = await get_account_info(account)
            account.balance = response["subscription_credits"]
            account.subscription = response["plan_type"]
            account.subscription_end_at = response["plan_ends_at"]
            await account.save()
        except Exception as e:
            logger.error(f"Error updating account {account.id} balance: {e}")
