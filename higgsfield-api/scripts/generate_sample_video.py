#!/usr/bin/env python3
"""
Submit a sample image-to-video job through the Higgsfield integration and download the resulting video.

This script uploads an image to Higgsfield, generates a video using the specified motion preset,
and downloads the result. Multiple output formats (mp4, webp) are downloaded when available.

This script automatically handles authentication - if no valid account exists, it will launch
Playwright to log in.
"""

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.repository.core import init_db
from src.services.higgsfield import (
    generate_video,
    get_job_set_id,
    get_last_used_account,
    get_token,
    upload_image,
    MOTION_ID_PARAMS,
    FRAME_MAPPING,
)

# Import auth utilities from manage_accounts
from manage_accounts import (
    AUTH_JSON_PATH,
    LOGIN_EMAIL,
    auth_state_has_valid_token,
    capture_auth,
    add_account_to_db,
)

logger = logging.getLogger("higgsfield.video")

DEFAULT_OUTPUT_DIR = Path("sample_outputs")


# ─────────────────────────────────────────────────────────────────────────────
# Auto-Authentication
# ─────────────────────────────────────────────────────────────────────────────


async def ensure_authenticated_account():
    """
    Ensure we have a valid authenticated account.
    
    If no account exists or the existing session is invalid, automatically
    runs the Playwright login flow and adds the account to the database.
    
    Returns:
        HiggsfieldAccount: A valid, authenticated account
    """
    # First, try to get an existing account
    account = await get_last_used_account()
    
    if account:
        # Verify the account's token is still valid
        try:
            await get_token(account)
            logger.info("Using existing account: %s", account.username)
            return account
        except Exception as e:
            logger.warning("Existing account token invalid: %s", e)
            logger.info("Will re-authenticate...")
    
    # No valid account - need to authenticate
    logger.info("No valid account found. Starting authentication flow...")
    
    # Check if we have valid auth.json already
    if not auth_state_has_valid_token(AUTH_JSON_PATH):
        logger.info("Launching Playwright for login...")
        capture_auth(force=True)
    
    # Add the account to the database
    username = LOGIN_EMAIL
    if not username:
        raise RuntimeError(
            "Cannot auto-authenticate: HIGGSFIELD_LOGIN_EMAIL not set. "
            "Please set it in .env.credentials or run 'python manage_accounts.py login' manually."
        )
    
    await add_account_to_db(username, AUTH_JSON_PATH, inactive=False)
    
    # Now get the account
    account = await get_last_used_account()
    if not account:
        raise RuntimeError("Failed to create account after authentication.")
    
    logger.info("Successfully authenticated as: %s", account.username)
    return account
SUPPORTED_MEDIA_SUFFIXES = {".mp4", ".webp", ".gif"}

# Available motions with descriptions
MOTION_DESCRIPTIONS: Dict[str, str] = {
    "GENERAL": "General purpose motion, works well with most images",
    "DISINTEGRATION": "Subject disintegrates into particles",
    "EARTH_ZOOM_OUT": "Camera zooms out from Earth view",
    "EYES_IN": "Camera zooms into the subject's eyes",
    "FACE_PUNCH": "Dynamic face punch effect",
    "ARC_RIGHT": "Camera arcs to the right around subject",
    "HANDHELD": "Simulates handheld camera movement",
    "BUILDING_EXPLOSION": "Dramatic building explosion effect",
    "STATIC": "Minimal camera movement, subtle animation",
    "TURNING_METAL": "Metallic turning/rotation effect",
    "3D_ROTATION": "3D rotation around subject",
    "SNORRICAM": "Snorricam (body-mounted camera) effect",
}

MOTIONS = list(MOTION_ID_PARAMS.keys())
MODELS = ["lite", "standard", "turbo"]
DURATIONS = list(FRAME_MAPPING.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Higgsfield video from a local image and download the result.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --image photo.jpg --prompt "A cinematic push-in shot"
  %(prog)s --image photo.jpg --motion DISINTEGRATION --duration 5
  %(prog)s --image photo.jpg --model turbo --motion 3D_ROTATION
  %(prog)s --list-motions

Available motions can be listed with --list-motions.
""",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to the source image file (required unless --list-motions).",
    )
    parser.add_argument(
        "--prompt",
        default="A cinematic push-in shot",
        help="Text prompt to guide the video generation.",
    )
    parser.add_argument(
        "--motion",
        default="GENERAL",
        choices=MOTIONS,
        help="Motion preset to use. Use --list-motions to see descriptions.",
    )
    parser.add_argument(
        "--model",
        default="lite",
        choices=MODELS,
        help="Higgsfield model variant: lite (fast), standard (balanced), turbo (quality).",
    )
    parser.add_argument(
        "--duration",
        default="3",
        choices=DURATIONS,
        help="Video duration in seconds.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic seed (1-1000000). Random if not provided.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where downloaded assets will be stored using their original filenames.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between job status checks.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum seconds to wait for the job to complete.",
    )
    parser.add_argument(
        "--use-unlim",
        dest="use_unlim",
        action="store_true",
        help="Use unlimited credits mode (default).",
    )
    parser.add_argument(
        "--no-use-unlim",
        dest="use_unlim",
        action="store_false",
        help="Disable unlimited credits mode.",
    )
    parser.set_defaults(use_unlim=True)
    parser.add_argument(
        "--list-motions",
        action="store_true",
        help="List all available motion presets and exit.",
    )
    return parser.parse_args()


def list_motions() -> None:
    """Print all available motion presets with descriptions."""
    print("Available Motion Presets:\n")
    for motion in MOTIONS:
        desc = MOTION_DESCRIPTIONS.get(motion, "No description available")
        print(f"  {motion}")
        print(f"      {desc}")
    print(f"\nTotal: {len(MOTIONS)} motions")
    print("\nUse --motion <NAME> to select a preset.")


# ─────────────────────────────────────────────────────────────────────────────
# Media URL Extraction (same pattern as image script)
# ─────────────────────────────────────────────────────────────────────────────


def _collect_media_urls(payload: Any, found: list[str]) -> None:
    """Recursively gather every URL-like string from the payload."""
    if isinstance(payload, str):
        if payload.startswith("http"):
            found.append(payload)
        return

    if isinstance(payload, Mapping):
        url = payload.get("url")
        if isinstance(url, str) and url.startswith("http"):
            found.append(url)

        for value in payload.values():
            _collect_media_urls(value, found)
        return

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            _collect_media_urls(item, found)


def _dedupe_preserve_order(urls: Sequence[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def extract_media_urls(payload: Any) -> list[str]:
    found: list[str] = []
    _collect_media_urls(payload, found)
    return _dedupe_preserve_order(found)


def filter_downloadable_urls(urls: Sequence[str]) -> list[str]:
    """Keep URLs that point to supported media formats (mp4/webp/gif)."""
    filtered: list[str] = []
    for url in urls:
        parsed = urlparse(url)
        suffix = Path(unquote(parsed.path)).suffix.lower()
        if suffix in SUPPORTED_MEDIA_SUFFIXES:
            filtered.append(url)
    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# Video Generation (direct API call for more control)
# ─────────────────────────────────────────────────────────────────────────────


async def generate_video_direct(
    prompt: str,
    image_path: Path,
    motion: str,
    model: str,
    duration: str,
    seed: Optional[int],
    use_unlim: bool,
    account,
) -> Dict[str, Any]:
    """Generate a video using the Higgsfield API with full control over parameters."""

    # Validate image
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if not image_path.is_file():
        raise ValueError(f"Image path is not a file: {image_path}")

    # Upload image
    logger.info("Uploading image: %s", image_path)
    image_data = await upload_image(str(image_path), account)
    logger.info("  Uploaded as ID: %s", image_data["id"])

    # Get motion configuration
    motion_params = MOTION_ID_PARAMS.get(motion)
    if not motion_params:
        raise ValueError(f"Unknown motion '{motion}'. Available: {', '.join(MOTIONS)}")

    # Get frame count for duration
    frames = FRAME_MAPPING.get(duration)
    if not frames:
        raise ValueError(f"Unknown duration '{duration}'. Available: {', '.join(DURATIONS)}")

    # Generate seed if not provided
    actual_seed = seed if seed is not None else random.randint(1, 1000000)

    # Build payload
    payload: Dict[str, Any] = {
        "params": {
            "prompt": prompt,
            "enhance_prompt": True,
            "model": model,
            "frames": frames,
            "input_image": {
                "id": image_data["id"],
                "url": image_data["url"],
                "type": "media_input",
            },
            "motion_id": motion_params["id"],
            "width": image_data.get("width"),
            "height": image_data.get("height"),
            "seed": actual_seed,
            "steps": 30,
            "use_unlim": use_unlim,
        },
        "use_unlim": use_unlim,
    }

    token = await get_token(account)

    async with httpx.AsyncClient(timeout=120) as client:
        url = "https://fnf.higgsfield.ai/jobs/image2video"
        headers = {"Authorization": f"Bearer {token}"}

        logger.debug("Video generation payload: %s", json.dumps(payload, indent=2))

        res = await client.post(url, headers=headers, json=payload)

        if res.status_code >= 400:
            try:
                error_body = res.json()
                logger.error("API error response: %s", json.dumps(error_body, indent=2))
            except json.JSONDecodeError:
                logger.error("API error response (text): %s", res.text)
            res.raise_for_status()

        try:
            data = res.json()
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from API: {e}")

        logger.info(
            "Successfully submitted video generation job. Job ID(s): %s",
            data.get("job_sets", []),
        )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Download and Wait Functions
# ─────────────────────────────────────────────────────────────────────────────


async def download_assets(urls: Sequence[str], output_dir: Path) -> list[Path]:
    """Download each URL to output_dir using its original filename."""
    if not urls:
        raise RuntimeError("No downloadable media URLs were returned by Higgsfield.")

    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    async with httpx.AsyncClient(timeout=120) as client:
        for idx, url in enumerate(urls, start=1):
            parsed = urlparse(url)
            filename = Path(unquote(parsed.path)).name or f"higgsfield_video_{idx}"
            destination = output_dir / filename

            response = await client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)
            saved_paths.append(destination)

    return saved_paths


async def wait_for_job(
    job_set_id: str,
    account,
    poll_interval: float,
    timeout: int,
) -> list[str]:
    """Poll Higgsfield until the job finishes and return all media URLs."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job_set = await get_job_set_id(job_set_id, account)
        job = job_set["jobs"][0]
        status = job["status"]
        logger.info("Job %s status: %s", job.get("id"), status)

        if status == "completed":
            result_payload = job.get("result") or job.get("results") or job
            urls = extract_media_urls(result_payload)
            if urls:
                return urls
            raise RuntimeError(f"No media URLs found in job result: {result_payload}")
        if status == "failed":
            raise RuntimeError(f"Higgsfield video job failed: {job.get('error')}")

        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Higgsfield video job {job_set_id} did not finish within {timeout} seconds.")


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Points
# ─────────────────────────────────────────────────────────────────────────────


async def async_main(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Handle --list-motions
    if args.list_motions:
        list_motions()
        return

    # Require --image if not listing motions
    if not args.image:
        raise ValueError("--image is required. Use --list-motions to see available motions.")

    if not args.image.exists():
        raise FileNotFoundError(f"Image file not found: {args.image}")

    await init_db()
    
    # Auto-authenticate if needed
    account = await ensure_authenticated_account()

    logger.info("Submitting Higgsfield video job...")
    logger.info("  Image: %s", args.image)
    logger.info("  Motion: %s", args.motion)
    logger.info("  Model: %s, Duration: %ss", args.model, args.duration)
    logger.info("  use_unlim: %s", args.use_unlim)

    job_set = await generate_video_direct(
        prompt=args.prompt,
        image_path=args.image,
        motion=args.motion,
        model=args.model,
        duration=args.duration,
        seed=args.seed,
        use_unlim=args.use_unlim,
        account=account,
    )

    try:
        job_set_id = job_set["job_sets"][0]["id"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Higgsfield response: {job_set}") from exc

    logger.info("Job set ID: %s", job_set_id)

    media_urls = await wait_for_job(
        job_set_id=job_set_id,
        account=account,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )

    downloadable_urls = filter_downloadable_urls(media_urls)
    if downloadable_urls:
        logger.info("Found %d downloadable assets (mp4/webp/gif).", len(downloadable_urls))
    else:
        logger.warning("No mp4/webp/gif URLs reported; downloading all available URLs instead.")
        downloadable_urls = media_urls

    saved_paths = await download_assets(downloadable_urls, args.output_dir)
    for path in saved_paths:
        logger.info("Saved %s", path.resolve())


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        logger.warning("Cancelled by user.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate video: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
