import asyncio
import json
import logging

import httpx

from ..repository.models.client import Client
from ..repository.models.task import Task
from ..utils.security import create_hmac_sha256_signature

logger = logging.getLogger("higgsfield")


async def send_results_to_client(retries: int = 10, delay: int = 60):
    """
    Send the results of finished tasks to a client endpoint, with optional retries and delay.

    This function looks for tasks that are either 'failed' or 'success' but haven't been
    delivered yet (`is_delivered=False`) and have remaining retries (`retries < max_retries`).
    It then marks each task with a `'_retry'` suffix in its status and creates an asynchronous
    subtask to attempt delivery via `send_task_with_retry`.

    :param retries: The maximum number of retry attempts. Defaults to 10.
    :type retries: int
    :param delay: The base delay (in seconds) between retries, used with exponential backoff.
    :type delay: int

    :return: None
    :rtype: None
    """
    finished_tasks = await Task.filter(
        status__in=["failed", "success"], is_delivered=False, retries__lt=retries
    ).order_by("id")

    if not finished_tasks:
        return

    logger.info(f"***   Received {len(finished_tasks)} Finished Tasks   ***")

    for task in finished_tasks:
        task.status = task.status + "_retry"
        await task.save()
        asyncio.create_task(send_task_with_retry(task, retries, delay))


async def send_task_with_retry(task: Task, retries: int = 10, delay: int = 60):
    """
    Attempt to send a task's result to the client's URL with multiple retry attempts.

    1. Retrieves the associated `Client` record for the task.
    2. If the client has no URL, logs an error, sets the task retries to the maximum, and stops.
    3. Attempts to send a POST request containing the task's result data (JSON format) to the
       client's URL, using an HMAC SHA-256 signature in the headers.
    4. If the request fails, logs an error, updates the task's status, increments `task.retries`,
       and waits with exponential backoff before retrying.
    5. If all attempts fail, logs a final error message indicating delivery failure.

    :param task: A `Tasks` model instance representing the completed task to deliver.
    :type task: Tasks
    :param retries: The maximum number of retry attempts. Defaults to 10.
    :type retries: int
    :param delay: The base delay (in seconds) between retries, used with exponential backoff.
    :type delay: int

    :return: None
    :rtype: None
    """
    client = await Client.get(id=task.client_id)
    if not client.url:
        # No webhook URL - mark as delivered (for local clients)
        task.is_delivered = True
        task.status = task.status.split("_")[0]  # Remove _retry suffix
        await task.save()
        logger.debug(f"Task {task.task_id} has no webhook URL - marked as delivered (local client)")
        return

    async with httpx.AsyncClient() as httpx_client:
        for attempt in range(task.retries, retries):
            try:
                code = 200
                result_dict = {
                    "status": task.status.split("_")[0],
                    "task_id": str(task.task_id),
                    "type": str(task.type),
                }

                if task.status.split("_")[0] == "failed":
                    code = 400
                    result_dict["message"] = task.result
                else:
                    result_dict["result"] = task.result

                if task.metadata:
                    result_dict["metadata"] = task.metadata

                result = {"code": code, "data": result_dict}

                signature = create_hmac_sha256_signature(
                    client.token, json.dumps(result, sort_keys=True)
                )

                response = await httpx_client.post(
                    client.url,
                    json=result,
                    headers={"X-Signature": signature},
                    timeout=30,
                )
                logger.info(f"Task ({task.task_id}) is Sent")
                response.raise_for_status()

                task.is_delivered = True
                task.update_datetime()
                task.status = task.status.split("_")[0]
                await task.save()
                logger.info(f"***   Task({task.task_id}) is Sent   ***")
                return
            except Exception as e:
                task.status = task.status.split("_")[0] + "_retry"
                await task.save()
                logger.error(
                    f"***   Sending Task({task.task_id}) Error on attempt {attempt + 1}: {str(e)}   ***"
                )

                await asyncio.sleep(delay * (2**attempt))

                task.retries += 1
                await task.save()

    task.status = task.status.split("_")[0]
    logger.error(f"***   Final delivery attempt failed for Task({task.task_id})   ***")
