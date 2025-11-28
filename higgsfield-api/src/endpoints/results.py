"""Task status and management endpoints."""

from datetime import timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from tortoise.exceptions import DoesNotExist

from ..repository.models.client import Client
from ..repository.models.task import Task
from .auth.security import validate_client_by_token
from .higgsfield.router import TaskStatus

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Response Models
# ─────────────────────────────────────────────────────────────────────────────


class TaskStatusResponse(BaseModel):
    """Response model for task status endpoint (matching official API style)."""

    request_id: str = Field(..., description="Unique task identifier (UUID)")
    status: TaskStatus = Field(..., description="Current task status")
    status_url: str = Field(..., description="URL to check task status")
    cancel_url: str = Field(..., description="URL to cancel the task")
    result: Optional[List[str]] = Field(
        None, description="Result URLs when completed"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[str] = Field(None, description="Task creation timestamp (ISO 8601)")
    started_at: Optional[str] = Field(None, description="Task start timestamp (ISO 8601)")
    finished_at: Optional[str] = Field(None, description="Task completion timestamp (ISO 8601)")
    task_type: Optional[str] = Field(None, description="Type of task (t2i, soul, i2v)")


class CancelResponse(BaseModel):
    """Response model for task cancellation."""

    request_id: str = Field(..., description="Unique task identifier (UUID)")
    status: TaskStatus = Field(..., description="New task status after cancellation")
    message: str = Field(..., description="Cancellation status message")


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def _map_status_to_enum(db_status: str) -> TaskStatus:
    """Map database status to API TaskStatus enum."""
    mapping = {
        "pending": TaskStatus.QUEUED,
        "starting": TaskStatus.QUEUED,
        "processing": TaskStatus.IN_PROGRESS,
        "success": TaskStatus.COMPLETED,
        "failed": TaskStatus.FAILED,
        "retry": TaskStatus.QUEUED,
    }
    return mapping.get(db_status, TaskStatus.QUEUED)


def _build_status_url(task_id: str) -> str:
    """Build the status URL for a task."""
    return f"/api/task/{task_id}/status"


def _build_cancel_url(task_id: str) -> str:
    """Build the cancel URL for a task."""
    return f"/api/task/{task_id}/cancel"


def _format_datetime(dt) -> Optional[str]:
    """Format a datetime to ISO 8601 string."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Task Status Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/task/{task_id}/status", response_model=TaskStatusResponse, tags=["Task Management"])
async def get_task_status(
    task_id: str,
    client: Client = Depends(validate_client_by_token),
):
    """
    Get the status of a generation task.

    Returns detailed status information including:
    - Current status (queued, in_progress, completed, failed, canceled)
    - Result URLs when completed
    - Error message if failed
    - Timestamps for task lifecycle

    Poll this endpoint to check task progress.
    """
    try:
        task = await Task.get(task_id=task_id)

        # Verify task belongs to client
        task_client = await task.client
        if task_client.id != client.id:
            raise HTTPException(status_code=404, detail="Task not found")

        status = _map_status_to_enum(task.status)
        task_id_str = str(task.task_id)

        return TaskStatusResponse(
            request_id=task_id_str,
            status=status,
            status_url=_build_status_url(task_id_str),
            cancel_url=_build_cancel_url(task_id_str),
            result=task.result if status == TaskStatus.COMPLETED else None,
            error=task.message if status == TaskStatus.FAILED else None,
            created_at=_format_datetime(task.created_at),
            started_at=_format_datetime(task.started_at),
            finished_at=_format_datetime(task.finished_at),
            task_type=task.type,
        )

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task status: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Legacy Task Result Endpoint (backwards compatibility)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/task/{task_id}", tags=["Task Management"])
async def get_task_result(
    task_id: str,
    client: Client = Depends(validate_client_by_token),
):
    """
    Get the result of a completed task (legacy endpoint).

    For more detailed status information, use GET /api/task/{task_id}/status instead.
    """
    try:
        task = await Task.get(task_id=task_id)

        # Verify task belongs to client
        task_client = await task.client
        if task_client.id != client.id:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": str(task.task_id),
            "status": task.status,
            "result": task.result,
        }

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")


# ─────────────────────────────────────────────────────────────────────────────
# Task Cancel Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/task/{task_id}/cancel", response_model=CancelResponse, tags=["Task Management"])
async def cancel_task(
    task_id: str,
    client: Client = Depends(validate_client_by_token),
):
    """
    Cancel a pending or in-progress task.

    Only tasks in 'pending' or 'processing' status can be canceled.
    Completed or failed tasks cannot be canceled.

    Returns 202 Accepted when cancellation is initiated.
    """
    try:
        task = await Task.get(task_id=task_id)

        # Verify task belongs to client
        task_client = await task.client
        if task_client.id != client.id:
            raise HTTPException(status_code=404, detail="Task not found")

        # Check if task can be canceled
        cancelable_statuses = {"pending", "starting", "processing"}
        if task.status not in cancelable_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel task with status '{task.status}'. Only pending or processing tasks can be canceled.",
            )

        # Mark as canceled
        task.status = "failed"
        task.message = "Canceled by user"
        await task.save()

        return CancelResponse(
            request_id=str(task.task_id),
            status=TaskStatus.CANCELED,
            message="Task cancellation initiated",
        )

    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error canceling task: {str(e)}")
