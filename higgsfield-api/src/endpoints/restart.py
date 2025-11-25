import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from pydantic import BaseModel
from tortoise.exceptions import DoesNotExist

from ..repository.models.client import Client
from ..repository.models.task import Task
from .auth.security import validate_client_by_token

logger = logging.getLogger("higgsfield")
router = APIRouter()


class RestartResponse(BaseModel):
    """Response model for restart."""

    task_id: str
    status: str
    message: str


@router.post("/task/restart/", response_model=RestartResponse)
async def restart_task(
    task_id: str = Form(...),
    metadata: Optional[str] = Form(""),
    client: Client = Depends(validate_client_by_token),
):
    """
    Restart a failed or completed task by resetting its status to 'pending'.

    Args:
        task_id: The UUID of the task to restart
        client: Authenticated client (injected by dependency)

    Returns:
        JSON response with success/error message
    """
    try:
        if metadata:
            metadata = json.loads(metadata)
        else:
            metadata = {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    try:
        task = await Task.get(task_id=task_id)

        new_metadata = task.metadata
        new_metadata.update(metadata)

        new_task = await Task.create(
            type=task.type,
            parameters_json=task.parameters_json,
            client=client,
            metadata=new_metadata,
        )

        logger.info(f"***   Task {task.task_id} Restarted: {new_task.task_id}   ***")
        return RestartResponse(
            task_id=str(new_task.task_id),
            status="success",
            message="Task restarted successfully",
        )

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        logger.error(f"***   Error restarting task {task_id}: {str(e)}   ***")
        raise HTTPException(status_code=500, detail="Internal server error")
