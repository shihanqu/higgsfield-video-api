"""Higgsfield API endpoints for text-to-image, Soul model, and image-to-video generation."""

import json
import logging
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from config import IMAGE_STORAGE_PATH

from ...repository.models.client import Client
from ...repository.models.task import Task
from ...utils.image_processing import save_byte_file
from ..auth.security import validate_client_by_token

logger = logging.getLogger("higgsfield")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Enums - Full CLI parity
# ─────────────────────────────────────────────────────────────────────────────


class ImageModel(str, Enum):
    """Available models for text-to-image generation."""

    NANO_BANANA_2 = "nano-banana-2"
    FLUX_2 = "flux-2"
    SEEDREAM = "seedream"
    TEXT2IMAGE = "text2image"
    TEXT2IMAGE_GPT = "text2image-gpt"
    FLUX_KONTEXT = "flux-kontext"
    CANVAS = "canvas"
    CANVAS_SOUL = "canvas-soul"
    WAN2_2_IMAGE = "wan2-2-image"
    NANO_BANANA = "nano-banana"
    NANO_BANANA_ANIMAL = "nano-banana-animal"
    KEYFRAMES_FACESWAP = "keyframes-faceswap"
    QWEN_CAMERA_CONTROL = "qwen-camera-control"
    VIRAL_TRANSFORM_IMAGE = "viral-transform-image"
    GAME_DUMP = "game-dump"
    REVE = "reve"


class AspectRatio(str, Enum):
    """Aspect ratio options for image generation."""

    SQUARE = "1:1"
    PORTRAIT_3_4 = "3:4"
    LANDSCAPE_4_3 = "4:3"
    WIDESCREEN = "16:9"
    VERTICAL = "9:16"


class SoulAspectRatio(str, Enum):
    """Extended aspect ratios for Soul model (includes 2:3 and 3:2)."""

    SQUARE = "1:1"
    PORTRAIT_3_4 = "3:4"
    LANDSCAPE_4_3 = "4:3"
    PORTRAIT_2_3 = "2:3"
    LANDSCAPE_3_2 = "3:2"
    WIDESCREEN = "16:9"
    VERTICAL = "9:16"


class Resolution(str, Enum):
    """Resolution options for standard image generation."""

    RES_1K = "1k"
    RES_2K = "2k"


class SoulResolution(str, Enum):
    """Resolution options for Soul model."""

    RES_720P = "720p"
    RES_1080P = "1080p"


class SoulBatchSize(int, Enum):
    """Batch size options for Soul model."""

    ONE = 1
    FOUR = 4


class VideoModel(str, Enum):
    """Models for video generation."""

    LITE = "lite"
    STANDARD = "standard"
    TURBO = "turbo"


class VideoMotion(str, Enum):
    """Motion presets for video generation."""

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


class VideoDuration(str, Enum):
    """Duration options for video generation."""

    SECONDS_3 = "3"
    SECONDS_5 = "5"


class TaskStatus(str, Enum):
    """Task status enum matching official API."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    NSFW = "nsfw"


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Request Models
# ─────────────────────────────────────────────────────────────────────────────


class TextToImageRequest(BaseModel):
    """Request body for text-to-image generation."""

    prompt: str = Field(..., description="Text prompt for image generation")
    model: ImageModel = Field(
        default=ImageModel.NANO_BANANA_2,
        description="Model to use for generation",
    )
    aspect_ratio: AspectRatio = Field(
        default=AspectRatio.LANDSCAPE_4_3,
        description="Aspect ratio for the generated image",
    )
    seed: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="Deterministic seed (1-1000000). Random if not provided.",
    )
    guidance_scale: float = Field(
        default=7.5,
        ge=1.0,
        le=20.0,
        description="Guidance scale (1-20)",
    )
    use_unlim: bool = Field(
        default=True,
        description="Use unlimited credits mode",
    )
    resolution: Resolution = Field(
        default=Resolution.RES_2K,
        description="Output resolution",
    )
    num_images: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate (1-4)",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata as JSON object",
    )


class SoulGenerationRequest(BaseModel):
    """Request body for Soul model image generation."""

    prompt: str = Field(..., description="Text prompt for image generation")
    aspect_ratio: SoulAspectRatio = Field(
        default=SoulAspectRatio.LANDSCAPE_4_3,
        description="Aspect ratio (Soul supports additional 2:3 and 3:2)",
    )
    style: Optional[str] = Field(
        default="general",
        description="Style preset name (e.g., 'realistic', 'grunge', 'y2k')",
    )
    style_id: Optional[str] = Field(
        default=None,
        description="Style preset UUID (overrides style name if provided)",
    )
    style_strength: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Strength of the style preset (0.0-1.0)",
    )
    resolution: SoulResolution = Field(
        default=SoulResolution.RES_720P,
        description="Resolution preset (720p or 1080p)",
    )
    batch_size: SoulBatchSize = Field(
        default=SoulBatchSize.ONE,
        description="Number of images to generate (1 or 4)",
    )
    enhance_prompt: bool = Field(
        default=True,
        description="Automatically enhance the prompt",
    )
    negative_prompt: str = Field(
        default="",
        description="Negative prompt to avoid certain elements",
    )
    seed: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="Deterministic seed (1-1000000). Random if not provided.",
    )
    steps: int = Field(
        default=50,
        ge=10,
        le=100,
        description="Number of inference steps",
    )
    sample_shift: float = Field(
        default=4.0,
        ge=0.0,
        le=10.0,
        description="Sample shift parameter",
    )
    sample_guide_scale: float = Field(
        default=4.0,
        ge=0.0,
        le=10.0,
        description="Sample guide scale parameter",
    )
    use_unlim: bool = Field(
        default=True,
        description="Use unlimited credits mode",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata as JSON object",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Response Models
# ─────────────────────────────────────────────────────────────────────────────


class TaskResponse(BaseModel):
    """Response model for task creation (matching official API style)."""

    request_id: str = Field(..., description="Unique task identifier (UUID)")
    status: TaskStatus = Field(..., description="Current task status")
    status_url: str = Field(..., description="URL to check task status")
    cancel_url: str = Field(..., description="URL to cancel the task")
    message: Optional[str] = Field(None, description="Additional status message")


class TaskStatusResponse(BaseModel):
    """Response model for task status endpoint."""

    request_id: str = Field(..., description="Unique task identifier (UUID)")
    status: TaskStatus = Field(..., description="Current task status")
    status_url: str = Field(..., description="URL to check task status")
    cancel_url: str = Field(..., description="URL to cancel the task")
    result: Optional[List[str]] = Field(
        None, description="Result URLs when completed"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[str] = Field(None, description="Task creation timestamp")
    finished_at: Optional[str] = Field(None, description="Task completion timestamp")


class StyleInfo(BaseModel):
    """Soul style preset information."""

    id: str = Field(..., description="Style UUID")
    name: str = Field(..., description="Style display name")
    description: str = Field(default="", description="Style description")
    preview_url: str = Field(..., description="Style preview image URL")


class StylesListResponse(BaseModel):
    """Response model for styles list endpoint."""

    styles: List[StyleInfo] = Field(..., description="List of available styles")
    total: int = Field(..., description="Total number of styles")


# ─────────────────────────────────────────────────────────────────────────────
# Soul Styles Loading
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent.parent
SOUL_STYLES_FILE = SCRIPT_DIR / "scripts" / "reference_input" / "soul_styles.json"

_SOUL_STYLES_CACHE: Optional[List[Dict[str, str]]] = None


def load_soul_styles() -> List[Dict[str, str]]:
    """Load Soul styles from the reference JSON file (cached)."""
    global _SOUL_STYLES_CACHE
    if _SOUL_STYLES_CACHE is not None:
        return _SOUL_STYLES_CACHE

    if not SOUL_STYLES_FILE.exists():
        logger.warning("Soul styles file not found: %s", SOUL_STYLES_FILE)
        return []

    with open(SOUL_STYLES_FILE, encoding="utf-8") as f:
        _SOUL_STYLES_CACHE = json.load(f)

    return _SOUL_STYLES_CACHE


def resolve_style_id(style_name: Optional[str], style_id: Optional[str]) -> Optional[str]:
    """Resolve style_id from either style_id or style name."""
    if style_id:
        return style_id

    if not style_name:
        return None

    styles = load_soul_styles()
    style_key = style_name.lower().replace(" ", "_").replace("'", "").replace("-", "_")

    for s in styles:
        # Match by normalized name
        s_key = s["name"].lower().replace(" ", "_").replace("'", "").replace("-", "_")
        if s_key == style_key:
            return s["id"]
        # Match by exact name (case-insensitive)
        if s["name"].lower() == style_name.lower():
            return s["id"]
        # Match by ID
        if s["id"] == style_name:
            return s["id"]

    # Default to "General" style if not found
    for s in styles:
        if s["name"].lower() == "general":
            return s["id"]

    return None


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


# ─────────────────────────────────────────────────────────────────────────────
# Text-to-Image Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/t2i/", response_model=TaskResponse, tags=["Higgsfield"])
async def generate_image(
    request: TextToImageRequest,
    client: Client = Depends(validate_client_by_token),
):
    """
    Generate an image from a text prompt.

    This endpoint creates an asynchronous task for image generation.
    Poll the status_url to check progress and retrieve results.

    **Supported Models:**
    - nano-banana-2 (default, fast)
    - flux-2 (requires seed)
    - seedream (high quality)
    - And many more...

    **Aspect Ratios:**
    - 1:1 (square)
    - 3:4 (portrait)
    - 4:3 (landscape, default)
    - 16:9 (widescreen)
    - 9:16 (vertical)
    """
    try:
        unique_task_id = str(uuid.uuid4())

        task_params = {
            "prompt": request.prompt,
            "model": request.model.value,
            "aspect_ratio": request.aspect_ratio.value,
            "guidance_scale": request.guidance_scale,
            "seed": request.seed,
            "use_unlim": request.use_unlim,
            "resolution": request.resolution.value,
            "batch_size": request.num_images,
        }

        task = await Task.create(
            task_id=unique_task_id,
            type="t2i",
            parameters_json=task_params,
            client=client,
            metadata=request.metadata or {},
        )

        logger.info(
            f"Higgsfield t2i task created: {task.task_id} for client: {client.username}"
        )

        return TaskResponse(
            request_id=str(task.task_id),
            status=TaskStatus.QUEUED,
            status_url=_build_status_url(str(task.task_id)),
            cancel_url=_build_cancel_url(str(task.task_id)),
            message="Image generation task created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating t2i task: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────────────────────────────────────────────────────
# Soul Model Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/soul/", response_model=TaskResponse, tags=["Higgsfield"])
async def generate_soul_image(
    request: SoulGenerationRequest,
    client: Client = Depends(validate_client_by_token),
):
    """
    Generate an image using the Soul model with style presets.

    The Soul model supports additional aspect ratios (2:3, 3:2) and style presets.
    Use GET /api/higgsfield/styles/ to list available styles.

    **Resolution Presets:**
    - 720p: Lower resolution, faster generation
    - 1080p: Higher resolution, slower generation

    **Style Strength:**
    - 0.0: No style influence
    - 1.0: Full style influence (default)
    """
    try:
        unique_task_id = str(uuid.uuid4())

        # Resolve style ID
        resolved_style_id = resolve_style_id(request.style, request.style_id)
        if not resolved_style_id:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve style '{request.style}'. Use GET /api/higgsfield/styles/ to see available styles.",
            )

        task_params = {
            "prompt": request.prompt,
            "aspect_ratio": request.aspect_ratio.value,
            "style_id": resolved_style_id,
            "style_strength": request.style_strength,
            "resolution": request.resolution.value,
            "batch_size": request.batch_size.value,
            "enhance_prompt": request.enhance_prompt,
            "negative_prompt": request.negative_prompt,
            "seed": request.seed,
            "steps": request.steps,
            "sample_shift": request.sample_shift,
            "sample_guide_scale": request.sample_guide_scale,
            "use_unlim": request.use_unlim,
        }

        task = await Task.create(
            task_id=unique_task_id,
            type="soul",
            parameters_json=task_params,
            client=client,
            metadata=request.metadata or {},
        )

        logger.info(
            f"Higgsfield Soul task created: {task.task_id} for client: {client.username}"
        )

        return TaskResponse(
            request_id=str(task.task_id),
            status=TaskStatus.QUEUED,
            status_url=_build_status_url(str(task.task_id)),
            cancel_url=_build_cancel_url(str(task.task_id)),
            message="Soul image generation task created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Soul task: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─────────────────────────────────────────────────────────────────────────────
# Soul Styles Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/styles/", response_model=StylesListResponse, tags=["Higgsfield"])
async def list_soul_styles():
    """
    List all available Soul style presets.

    Returns a list of styles that can be used with the Soul model endpoint.
    Use the style `id` as `style_id` or the `name` as `style` parameter.
    """
    styles_data = load_soul_styles()

    styles = [
        StyleInfo(
            id=s["id"],
            name=s["name"],
            description=s.get("description", ""),
            preview_url=s.get("preview_url", ""),
        )
        for s in styles_data
    ]

    return StylesListResponse(
        styles=styles,
        total=len(styles),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Image-to-Video Endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/i2v/", response_model=TaskResponse, tags=["Higgsfield"])
async def generate_video(
    image: UploadFile = File(..., description="Image file to generate video from"),
    prompt: Optional[str] = Form("A cinematic push-in shot", description="Prompt for the video"),
    motion: VideoMotion = Form(VideoMotion.GENERAL, description="Motion preset"),
    model: VideoModel = Form(VideoModel.LITE, description="Model variant"),
    duration: VideoDuration = Form(VideoDuration.SECONDS_3, description="Video duration"),
    seed: Optional[int] = Form(None, ge=1, le=1000000, description="Deterministic seed"),
    use_unlim: bool = Form(True, description="Use unlimited credits mode"),
    metadata: Optional[str] = Form(None, description="Additional metadata as JSON string"),
    client: Client = Depends(validate_client_by_token),
):
    """
    Generate a video from an image.

    Upload an image and specify motion parameters to create a video.
    The image is uploaded and stored, then processed asynchronously.

    **Models:**
    - lite: Fast generation
    - standard: Balanced quality/speed
    - turbo: Highest quality

    **Motion Presets:**
    - GENERAL: General purpose motion
    - DISINTEGRATION: Particle disintegration effect
    - STATIC: Minimal movement
    - And many more...
    """
    try:
        unique_task_id = str(uuid.uuid4())
        image_path = await save_byte_file(
            image, IMAGE_STORAGE_PATH, f"{unique_task_id}.png"
        )

        task_params = {
            "prompt": prompt,
            "motion": motion.value,
            "image_path": image_path,
            "model": model.value,
            "duration": duration.value,
            "seed": seed,
            "use_unlim": use_unlim,
        }

        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid JSON in metadata parameter",
                )

        task = await Task.create(
            task_id=unique_task_id,
            type="i2v",
            parameters_json=task_params,
            client=client,
            metadata=parsed_metadata,
        )

        logger.info(
            f"Higgsfield i2v task created: {task.task_id} for client: {client.username}"
        )

        return TaskResponse(
            request_id=str(task.task_id),
            status=TaskStatus.QUEUED,
            status_url=_build_status_url(str(task.task_id)),
            cancel_url=_build_cancel_url(str(task.task_id)),
            message="Video generation task created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating i2v task: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
