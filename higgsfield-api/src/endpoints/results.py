from fastapi import APIRouter, Depends, HTTPException
from tortoise.exceptions import DoesNotExist

from ..repository.models.client import Client
from ..repository.models.task import Task
from .auth.security import validate_client_by_token

router = APIRouter()


@router.get("/task/{task_id}")
async def get_task_result(
    task_id: str, client: Client = Depends(validate_client_by_token)
):
    try:
        task = await Task.get(task_id=task_id)
        return task.result
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
