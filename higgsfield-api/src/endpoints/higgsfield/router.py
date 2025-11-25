"""TTS (Text-to-Speech) endpoints for task creation."""

import json
import logging
import uuid
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from config import IMAGE_STORAGE_PATH

from ...repository.models.client import Client
from ...repository.models.task import Task
from ...utils.image_processing import save_byte_file
from ..auth.security import validate_client_by_token

logger = logging.getLogger("higgsfield")

router = APIRouter()


class HiggsfieldResponse(BaseModel):
    """Response model for Higgsfield tasks."""

    task_id: str
    status: str
    message: str


class Motions(str, Enum):
    """Motion types for the video."""

    GENERAL = "GENERAL"
    DISINTEGRATION = "DISINTEGRATION"
    EARTH_ZOOM_OUT = "EARTH_ZOOM_OUT"
    EYES_IN = "EYES_IN"
    FACE_PUNCH = "FACE_PUNCH"
    ARC_RIGHT = "ARC_RIGHT"
    HANDHELD = "HANDHELD"
    BUILDING_EXPLOSION = "BUILDING_EXPLOSION"
    STATIC = "STATIC"
    TURNING_METAL = "TURNING_METAL"
    THREE_D_ROTATION = "3D_ROTATION"
    SNORRICAM = "SNORRICAM"


class Models(str, Enum):
    """Models for the video."""

    LITE = "lite"
    STANDARD = "standard"
    TURBO = "turbo"


class Duration(str, Enum):
    """Duration of the video."""

    d3 = "3"
    d5 = "5"


@router.post("/i2v/", response_model=HiggsfieldResponse, tags=["Higgsfield"])
async def generate_video(
    image: UploadFile = File(..., description="Image file to generate video"),
    prompt: Optional[str] = Form("", description="Prompt for the video"),
    motion: Motions = Form(Motions.GENERAL, description="Motion type for the video"),
    model: Models = Form(Models.LITE, description="Model type for the video"),
    duration: Duration = Form(Duration.d3, description="Duration of the video"),
    metadata: Optional[str] = Form(
        None, description="Additional metadata as JSON string"
    ),
    client: Client = Depends(validate_client_by_token),
):
    try:
        unique_task_id = str(uuid.uuid4())
        image_path = await save_byte_file(
            image, IMAGE_STORAGE_PATH, f"{unique_task_id}.png"
        )

        task_params = {
            "prompt": prompt,
            "motion": motion,
            "image_path": image_path,
            "model": model,
            "duration": duration,
        }

        task = await Task.create(
            task_id=unique_task_id,
            type="i2v",
            parameters_json=task_params,
            client=client,
            metadata=json.loads(metadata) if metadata else {},
        )

        logger.info(
            f"Higgsfield task created: {task.task_id} for client: {client.username}"
        )

        return HiggsfieldResponse(
            task_id=str(task.task_id),
            status="pending",
            message="Higgsfield generation task created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Higgsfield task: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
