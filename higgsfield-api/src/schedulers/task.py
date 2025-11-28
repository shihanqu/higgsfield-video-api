import asyncio
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx

# Add parent directories to path for config import
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from config import TASK_STATUS_REQUEST_DELAY

from ..repository.models.account import HiggsfieldAccount
from ..repository.models.task import Task
from ..services.higgsfield import (
    ensure_authenticated_account,
    generate_image,
    generate_video,
    get_account_info,
    get_job_set_id,
    get_last_used_account,
    get_token,
)

logger = logging.getLogger("higgsfield")


# ─────────────────────────────────────────────────────────────────────────────
# Soul Model Dimensions
# ─────────────────────────────────────────────────────────────────────────────

SOUL_RESOLUTION_DIMENSIONS: Dict[str, Dict[str, tuple]] = {
    "720p": {
        "1:1": (1152, 1152),
        "3:4": (1152, 1536),
        "4:3": (1536, 1152),
        "2:3": (1024, 1536),
        "3:2": (1536, 1024),
        "9:16": (864, 1536),
        "16:9": (1536, 864),
    },
    "1080p": {
        "1:1": (1536, 1536),
        "3:4": (1536, 2048),
        "4:3": (2048, 1536),
        "2:3": (1365, 2048),
        "3:2": (2048, 1365),
        "9:16": (1152, 2048),
        "16:9": (2048, 1152),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Image-to-Video Task Processing
# ─────────────────────────────────────────────────────────────────────────────


async def process_i2v_tasks(task: Task):
    """Process image-to-video generation tasks."""
    prompt = task.parameters_json.get("prompt", "")
    image_path = task.parameters_json.get("image_path")
    motion = task.parameters_json.get("motion")
    model = task.parameters_json.get("model")
    duration = task.parameters_json.get("duration")

    try:
        account = await ensure_authenticated_account()
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


# ─────────────────────────────────────────────────────────────────────────────
# Text-to-Image Task Processing
# ─────────────────────────────────────────────────────────────────────────────


async def process_t2i_tasks(task: Task):
    """Process text-to-image generation tasks."""
    prompt = task.parameters_json.get("prompt", "")
    model = task.parameters_json.get("model", "nano-banana-2")
    aspect_ratio = task.parameters_json.get("aspect_ratio", "4:3")
    guidance_scale = task.parameters_json.get("guidance_scale")
    seed = task.parameters_json.get("seed")
    use_unlim = task.parameters_json.get("use_unlim", True)

    logger.info(f"Submitting Higgsfield image job...")
    logger.info(f"  Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    logger.info(f"  Model: {model}, Aspect: {aspect_ratio}")
    logger.info(f"  use_unlim: {use_unlim}")

    try:
        account = await ensure_authenticated_account()
        task.account = account
        await task.save()

        job_set = await generate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            guidance_scale=guidance_scale,
            seed=seed,
            account=account,
            use_unlim=use_unlim,
        )
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        task.status = "failed"
        task.message = str(e)
        await task.save()
        return

    try:
        job_id = job_set["job_sets"][0]["id"]
        logger.info(f"Job set ID: {job_id}")
        task.status = "processing"
        task.api_task_id = job_id
        await task.save()
    except Exception as e:
        logger.error(f"Error updating image task: {e}")
        task.status = "failed"
        task.message = str(e)
        await task.save()
        return


# ─────────────────────────────────────────────────────────────────────────────
# Soul Model Task Processing
# ─────────────────────────────────────────────────────────────────────────────


async def process_soul_tasks(task: Task):
    """Process Soul model image generation tasks."""
    params = task.parameters_json

    prompt = params.get("prompt", "")
    aspect_ratio = params.get("aspect_ratio", "4:3")
    style_id = params.get("style_id")
    style_strength = params.get("style_strength", 1.0)
    resolution = params.get("resolution", "720p")
    batch_size = params.get("batch_size", 1)
    enhance_prompt = params.get("enhance_prompt", True)
    negative_prompt = params.get("negative_prompt", "")
    seed = params.get("seed")
    steps = params.get("steps", 50)
    sample_shift = params.get("sample_shift", 4.0)
    sample_guide_scale = params.get("sample_guide_scale", 4.0)
    use_unlim = params.get("use_unlim", True)

    try:
        account = await ensure_authenticated_account()
        task.account = account
        await task.save()

        # Get dimensions for resolution and aspect ratio
        resolution_dims = SOUL_RESOLUTION_DIMENSIONS.get(
            resolution, SOUL_RESOLUTION_DIMENSIONS["720p"]
        )
        dimensions = resolution_dims.get(aspect_ratio)
        if not dimensions:
            task.status = "failed"
            task.message = f"Unsupported aspect ratio '{aspect_ratio}' for Soul model"
            await task.save()
            return

        width, height = dimensions
        actual_seed = seed if seed is not None else random.randint(1, 1000000)

        # Build Soul model payload
        payload: Dict[str, Any] = {
            "params": {
                "quality": resolution,
                "aspect_ratio": aspect_ratio,
                "prompt": prompt,
                "enhance_prompt": enhance_prompt,
                "style_id": style_id,
                "fashion_factory_id": None,
                "style_strength": style_strength,
                "custom_reference_strength": 0.9,
                "seed": actual_seed,
                "width": width,
                "height": height,
                "steps": steps,
                "batch_size": batch_size,
                "sample_shift": sample_shift,
                "sample_guide_scale": sample_guide_scale,
                "negative_prompt": negative_prompt,
                "version": 3,
                "use_unlim": use_unlim,
            },
            "use_unlim": use_unlim,
        }

        token = await get_token(account)

        async with httpx.AsyncClient(timeout=120) as client:
            url = "https://fnf.higgsfield.ai/jobs/text2image-soul"
            headers = {"Authorization": f"Bearer {token}"}

            logger.debug(f"Soul model payload: {payload}")

            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()

            job_set = res.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"Soul API error: {e.response.status_code} - {e.response.text}")
        task.status = "failed"
        task.message = f"Soul API error: {e.response.status_code}"
        await task.save()
        return
    except Exception as e:
        logger.error(f"Error generating Soul image: {e}")
        task.status = "failed"
        task.message = str(e)
        await task.save()
        return

    try:
        job_id = job_set["job_sets"][0]["id"]
        task.status = "processing"
        task.api_task_id = job_id
        await task.save()
        logger.info(f"Soul task {task.task_id} submitted with job_id {job_id}")
    except Exception as e:
        logger.error(f"Error updating Soul task: {e}")
        task.status = "failed"
        task.message = str(e)
        await task.save()
        return


# ─────────────────────────────────────────────────────────────────────────────
# Task Status Checking
# ─────────────────────────────────────────────────────────────────────────────


async def check_task_status():
    """Check status of processing tasks and update with results."""
    tasks = await Task.filter(status="processing")
    for i, task in enumerate(tasks):
        # Add delay between requests to avoid hammering the API
        if i > 0 and TASK_STATUS_REQUEST_DELAY > 0:
            await asyncio.sleep(TASK_STATUS_REQUEST_DELAY)
        
        try:
            account = await task.account
            if not account:
                logger.warning(f"Task {task.task_id} has no associated account")
                continue

            job_set = await get_job_set_id(task.api_task_id, account)
            job = job_set["jobs"][0]
            status = job["status"]
            job_id = job.get("id", "unknown")
            
            logger.info(f"Job {job_id} status: {status}")

            if status == "completed":
                task.status = "success"
                # Extract result URLs - handle different result structures
                result = job.get("result") or job.get("results") or {}
                logger.debug(f"Raw result data: {result}")
                
                urls = []
                if isinstance(result, dict):
                    # Extract all URLs from the result structure
                    for key, value in result.items():
                        if isinstance(value, dict) and "url" in value:
                            urls.append(value["url"])
                            logger.info(f"  Found {key} URL: {value['url']}")
                        elif isinstance(value, str) and value.startswith("http"):
                            urls.append(value)
                            logger.info(f"  Found {key} URL: {value}")
                    
                    # Also check for top-level url
                    if "url" in result:
                        top_url = result["url"]
                        if top_url not in urls:
                            urls.append(top_url)
                            logger.info(f"  Found top-level URL: {top_url}")
                            
                elif isinstance(result, list):
                    urls = result
                    for url in urls:
                        logger.info(f"  Found URL: {url}")
                else:
                    urls = [str(result)]
                
                task.result = urls if urls else [str(result)]
                task.update_datetime()
                await task.save()
                logger.info(f"Task {task.task_id} completed with {len(task.result)} result(s)")
                for url in task.result:
                    logger.info(f"  Result: {url}")

            elif status == "failed":
                task.status = "failed"
                task.message = job.get("error") or "Unknown error"
                task.update_datetime()
                await task.save()
                logger.error(f"Task {task.task_id} failed: {task.message}")

        except Exception as e:
            logger.error(f"Error getting job set for task {task.task_id}: {e}")
            continue  # Continue with other tasks instead of returning


# ─────────────────────────────────────────────────────────────────────────────
# Account Management
# ─────────────────────────────────────────────────────────────────────────────


# Note: Automatic auth refresh removed due to Playwright/Python 3.13 compatibility issues.
# To refresh an expired session, run: python scripts/manage_accounts.py login --force


async def update_account_balance():
    """Update account balance information."""
    accounts = await HiggsfieldAccount.filter(is_active=True)
    for account in accounts:
        try:
            response = await get_account_info(account)
            account.balance = response.get("subscription_credits")
            account.subscription = response.get("plan_type")
            account.subscription_end_at = response.get("plan_ends_at")
            await account.save()
        except Exception as e:
            logger.error(f"Error updating account {account.id} balance: {e}")
