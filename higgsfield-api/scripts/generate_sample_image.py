#!/usr/bin/env python3
"""
Submit a sample text-to-image job through the Higgsfield integration and save the outputs locally.

Supports both standard models (nano-banana-2, flux-2, etc.) and the Soul model (text2image-soul).
The Soul model has additional parameters like style presets and resolution settings.

Both the PNG and WEBP variants emitted by Higgsfield are downloaded into the sample outputs
directory using their original filenames. This script automatically handles authentication -
if no valid account exists, it will launch Playwright to log in.
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
    generate_image,
    get_job_set_id,
    get_last_used_account,
    get_token,
    upload_image,
)

# Import auth utilities from manage_accounts
from manage_accounts import (
    AUTH_JSON_PATH,
    LOGIN_EMAIL,
    auth_state_has_valid_token,
    capture_auth,
    add_account_to_db,
)

logger = logging.getLogger("higgsfield.script")


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
SUPPORTED_MEDIA_SUFFIXES = {".png", ".webp"}

# ─────────────────────────────────────────────────────────────────────────────
# Soul Model Configuration
# ─────────────────────────────────────────────────────────────────────────────

SOUL_STYLES_FILE = SCRIPT_DIR / "reference_input" / "soul_styles.json"

# Soul model identifiers (with and without hyphens/underscores)
SOUL_MODEL_NAMES = {"text2image-soul", "text2image_soul", "soul"}

# Available aspect ratios for Soul model (superset of standard ratios)
SOUL_ASPECT_RATIOS = ["9:16", "16:9", "4:3", "3:4", "1:1", "2:3", "3:2"]

# Standard aspect ratios for non-Soul models
STANDARD_ASPECT_RATIOS = ["1:1", "3:4", "4:3", "16:9", "9:16"]

# Soul model dimensions by resolution and aspect ratio
SOUL_RESOLUTION_DIMENSIONS: Dict[str, Dict[str, tuple[int, int]]] = {
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


def load_soul_styles() -> Dict[str, Dict[str, str]]:
    """Load Soul styles from the reference JSON file."""
    if not SOUL_STYLES_FILE.exists():
        logger.warning("Soul styles file not found: %s", SOUL_STYLES_FILE)
        return {}

    with open(SOUL_STYLES_FILE, encoding="utf-8") as f:
        styles_list: List[Dict[str, str]] = json.load(f)

    # Create lookup by name (lowercased, spaces replaced with underscores)
    styles: Dict[str, Dict[str, str]] = {}
    for style in styles_list:
        key = style["name"].lower().replace(" ", "_").replace("'", "").replace("-", "_")
        styles[key] = {
            "id": style["id"],
            "name": style["name"],
            "url": style["preview_url"],
            "description": style.get("description", ""),
        }
        # Also allow lookup by ID directly
        styles[style["id"]] = styles[key]

    return styles


# Load Soul styles at module level (lazy - only if file exists)
SOUL_STYLES: Dict[str, Dict[str, str]] = {}


def get_soul_styles() -> Dict[str, Dict[str, str]]:
    """Get Soul styles, loading them on first access."""
    global SOUL_STYLES
    if not SOUL_STYLES:
        SOUL_STYLES = load_soul_styles()
    return SOUL_STYLES


def is_soul_model(model: str) -> bool:
    """Check if the model is a Soul model."""
    normalized = model.lower().strip()
    return normalized in SOUL_MODEL_NAMES


# ─────────────────────────────────────────────────────────────────────────────
# Argument Parsing
# ─────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a sample Higgsfield text-to-image output and download it locally.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples (Standard Models):
  %(prog)s --prompt "A sunset landscape"
  %(prog)s --model flux-2 --aspect-ratio 16:9

Examples (With Input Images - img2img):
  %(prog)s --prompt "Make it sunset" --input-image photo.jpg
  %(prog)s --prompt "Combine these" --input-image img1.jpg --input-image img2.jpg

Examples (Soul Model):
  %(prog)s --model soul --prompt "A portrait" --style realistic
  %(prog)s --model text2image-soul --resolution 1080p --style-id <uuid>
  %(prog)s --model soul --list-styles

Soul-specific options (--style, --style-id, --style-strength, --resolution,
--enhance-prompt, --negative-prompt, --batch-size) are only used when
--model is 'soul' or 'text2image-soul'.

Input images (--input-image) are currently supported for standard models only.
""",
    )

    # ─── Common Arguments ────────────────────────────────────────────────────
    parser.add_argument(
        "--prompt",
        default="A cinematic photograph of a neon-lit cyberpunk city street at dusk",
        help="Prompt to render.",
    )
    parser.add_argument(
        "--model",
        default="nano-banana-2",
        help=(
            "Higgsfield model to use. Standard models: nano-banana-2, flux-2, seedream, etc. "
            "Soul model: 'soul' or 'text2image-soul'."
        ),
    )
    parser.add_argument(
        "--aspect-ratio",
        default="1:1",
        help=(
            "Aspect ratio. Standard: 1:1, 3:4, 4:3, 16:9, 9:16. "
            "Soul also supports: 2:3, 3:2. Default: 1:1"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic seed. Soul: 1-1000000. Random if not provided.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where downloaded assets will be stored.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Seconds between status checks.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum seconds to wait for the job to finish.",
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

    # ─── Standard Model Arguments ────────────────────────────────────────────
    parser.add_argument(
        "--guidance-scale",
        type=float,
        default=7.5,
        help="[Standard models] Guidance scale (typically 1-20).",
    )
    parser.add_argument(
        "--input-image",
        type=Path,
        action="append",
        dest="input_images",
        metavar="FILE",
        help=(
            "Input image for img2img generation. Can be specified multiple times. "
            "Images are uploaded to Higgsfield before generation."
        ),
    )

    # ─── Soul Model Arguments ────────────────────────────────────────────────
    soul_group = parser.add_argument_group(
        "Soul model options",
        "These options only apply when --model is 'soul' or 'text2image-soul'.",
    )
    soul_group.add_argument(
        "--style",
        default="general",
        metavar="NAME",
        help="Style preset name (e.g., 'realistic', 'grunge', 'y2k'). Use --list-styles to see all.",
    )
    soul_group.add_argument(
        "--style-id",
        default=None,
        metavar="UUID",
        help="Style preset UUID (overrides --style if provided).",
    )
    soul_group.add_argument(
        "--style-strength",
        type=float,
        default=1.0,
        help="Strength of the style preset (0.0 to 1.0). Default: 1.0",
    )
    soul_group.add_argument(
        "--resolution",
        default="720p",
        choices=["720p", "1080p"],
        help="Resolution preset (affects output dimensions). Default: 720p",
    )
    soul_group.add_argument(
        "--batch-size",
        type=int,
        default=1,
        choices=[1, 4],
        help="Number of images to generate (1 or 4). Default: 1",
    )
    soul_group.add_argument(
        "--enhance-prompt",
        dest="enhance_prompt",
        action="store_true",
        help="Automatically enhance the prompt (default for Soul).",
    )
    soul_group.add_argument(
        "--no-enhance-prompt",
        dest="enhance_prompt",
        action="store_false",
        help="Disable automatic prompt enhancement.",
    )
    parser.set_defaults(enhance_prompt=True)
    soul_group.add_argument(
        "--negative-prompt",
        default="",
        help="Negative prompt to avoid certain elements.",
    )
    soul_group.add_argument(
        "--steps",
        type=int,
        default=50,
        help="Number of inference steps. Default: 50",
    )
    soul_group.add_argument(
        "--sample-shift",
        type=float,
        default=4.0,
        help="Sample shift parameter. Default: 4.0",
    )
    soul_group.add_argument(
        "--sample-guide-scale",
        type=float,
        default=4.0,
        help="Sample guide scale parameter. Default: 4.0",
    )
    soul_group.add_argument(
        "--list-styles",
        action="store_true",
        help="List all available Soul styles and exit.",
    )

    return parser.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Soul Model Functions
# ─────────────────────────────────────────────────────────────────────────────


def list_styles() -> None:
    """Print all available Soul styles."""
    styles = get_soul_styles()
    if not styles:
        print("No styles loaded. Check that soul_styles.json exists.")
        return

    # Get unique styles (filter out ID-based duplicates)
    seen_ids = set()
    unique_styles = []
    for key, style in styles.items():
        if style["id"] not in seen_ids:
            seen_ids.add(style["id"])
            unique_styles.append((key, style))

    print(f"Available Soul Styles ({len(unique_styles)} total):\n")
    for key, style in sorted(unique_styles, key=lambda x: x[1]["name"].lower()):
        desc = style.get("description", "")
        if desc:
            print(f"  {key}: {style['name']}")
            print(f"      {desc[:80]}{'...' if len(desc) > 80 else ''}")
        else:
            print(f"  {key}: {style['name']}")
    print(f"\nUse --style <name> or --style-id <uuid> to select a style.")


def resolve_style_id(args: argparse.Namespace) -> str:
    """Resolve style_id from either --style-id or --style arguments."""
    styles = get_soul_styles()

    # If style_id is provided directly, use it
    if args.style_id:
        return args.style_id

    # Otherwise, look up by style name
    style_key = args.style.lower().replace(" ", "_").replace("'", "").replace("-", "_")
    style = styles.get(style_key)
    if style:
        return style["id"]

    # Try exact match on name
    for s in styles.values():
        if s["name"].lower() == args.style.lower():
            return s["id"]

    # List similar styles
    available = [s["name"] for s in styles.values() if "id" in s]
    available = list(set(available))[:10]  # Dedupe and limit
    raise ValueError(
        f"Unknown style '{args.style}'. "
        f"Some available styles: {', '.join(available)}... "
        f"Use --list-styles to see all."
    )


async def generate_image_soul(
    prompt: str,
    aspect_ratio: str,
    style_id: str,
    style_strength: float,
    seed: Optional[int],
    resolution: str,
    steps: int,
    sample_shift: float,
    sample_guide_scale: float,
    negative_prompt: str,
    enhance_prompt: bool,
    use_unlim: bool,
    batch_size: int,
    account,
) -> Dict[str, Any]:
    """Generate an image using the Soul model with its specific API structure."""

    # Look up dimensions based on resolution
    resolution_dims = SOUL_RESOLUTION_DIMENSIONS.get(resolution, SOUL_RESOLUTION_DIMENSIONS["720p"])
    dimensions = resolution_dims.get(aspect_ratio)
    if not dimensions:
        raise ValueError(
            f"Unsupported aspect ratio '{aspect_ratio}' for Soul model. "
            f"Supported values: {', '.join(SOUL_ASPECT_RATIOS)}"
        )
    width, height = dimensions

    actual_seed = seed if seed is not None else random.randint(1, 1000000)

    # Soul model payload structure
    payload: Dict[str, Any] = {
        "params": {
            "quality": resolution,  # API uses "quality" field but accepts resolution values
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

        logger.debug("Soul model payload: %s", json.dumps(payload, indent=2))

        res = await client.post(url, headers=headers, json=payload)
        res.raise_for_status()

        try:
            data = res.json()
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from Soul API: {e}")

        return data


# ─────────────────────────────────────────────────────────────────────────────
# Input Image Handling
# ─────────────────────────────────────────────────────────────────────────────

# Standard model dimensions by aspect ratio
STANDARD_ASPECT_TO_DIMENSIONS: Dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "3:4": (896, 1152),
    "4:3": (1152, 896),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}


async def upload_input_images(
    image_paths: List[Path],
    account,
) -> List[Dict[str, str]]:
    """Upload input images and return them in API format."""
    input_images: List[Dict[str, str]] = []

    for path in image_paths:
        if not path.exists():
            raise FileNotFoundError(f"Input image not found: {path}")
        if not path.is_file():
            raise ValueError(f"Input image path is not a file: {path}")

        logger.info("Uploading input image: %s", path)
        result = await upload_image(str(path), account)

        # Format for API: {"id": ..., "url": ..., "type": "media_input"}
        input_images.append({
            "id": result["id"],
            "url": result["url"],
            "type": "media_input",
        })
        logger.info("  Uploaded as ID: %s", result["id"])

    return input_images


async def generate_image_standard(
    prompt: str,
    model: str,
    aspect_ratio: str,
    guidance_scale: float,
    seed: Optional[int],
    use_unlim: bool,
    input_images: List[Dict[str, str]],
    account,
) -> Dict[str, Any]:
    """Generate an image using a standard model with optional input images."""

    dimensions = STANDARD_ASPECT_TO_DIMENSIONS.get(aspect_ratio)
    if not dimensions:
        raise ValueError(
            f"Unsupported aspect ratio '{aspect_ratio}'. "
            f"Supported values: {', '.join(STANDARD_ASPECT_TO_DIMENSIONS)}"
        )
    width, height = dimensions

    # Normalize model name to endpoint slug
    model_endpoint = model.strip().lower().replace("_", "-")

    # Generate seed if not provided (some models like flux-2 require it)
    actual_seed = seed if seed is not None else random.randint(1, 1000000)

    # Inner params payload
    params: Dict[str, Any] = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "width": width,
        "height": height,
        "batch_size": 1,
        "use_unlim": use_unlim,
        "resolution": "2k",
        "input_images": input_images,
        "enhance_prompt": True,
        "seed": actual_seed,
    }

    # Wrap in outer structure (required by API)
    payload: Dict[str, Any] = {
        "params": params,
        "use_unlim": use_unlim,
    }

    token = await get_token(account)

    async with httpx.AsyncClient(timeout=120) as client:
        url = f"https://fnf.higgsfield.ai/jobs/{model_endpoint}"
        headers = {"Authorization": f"Bearer {token}"}

        logger.debug("Standard model payload: %s", json.dumps(payload, indent=2))

        res = await client.post(url, headers=headers, json=payload)
        
        if res.status_code >= 400:
            # Try to get error details from response
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
            "Successfully submitted image generation job. Job ID(s): %s",
            data.get("job_sets", []),
        )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Common Functions
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
    """Keep URLs that point to supported media formats (png/webp)."""
    filtered: list[str] = []
    for url in urls:
        parsed = urlparse(url)
        suffix = Path(unquote(parsed.path)).suffix.lower()
        if suffix in SUPPORTED_MEDIA_SUFFIXES:
            filtered.append(url)
    return filtered


async def download_assets(urls: Sequence[str], output_dir: Path) -> list[Path]:
    """Download each URL to output_dir using its original filename."""
    if not urls:
        raise RuntimeError("No downloadable media URLs were returned by Higgsfield.")

    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    async with httpx.AsyncClient(timeout=120) as client:
        for idx, url in enumerate(urls, start=1):
            parsed = urlparse(url)
            filename = Path(unquote(parsed.path)).name or f"higgsfield_asset_{idx}"
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
            raise RuntimeError(f"Higgsfield job failed: {job.get('error')}")

        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Higgsfield job {job_set_id} did not finish within {timeout} seconds.")


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Points
# ─────────────────────────────────────────────────────────────────────────────


async def async_main(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Handle --list-styles (Soul-only, but allow it regardless)
    if args.list_styles:
        list_styles()
        return

    await init_db()
    
    # Auto-authenticate if needed
    account = await ensure_authenticated_account()

    # Determine if this is a Soul model request
    using_soul = is_soul_model(args.model)

    if using_soul:
        # Validate Soul-specific parameters
        if not 0.0 <= args.style_strength <= 1.0:
            raise ValueError("style_strength must be between 0.0 and 1.0")
        if args.seed is not None and not 1 <= args.seed <= 1000000:
            raise ValueError("seed must be between 1 and 1000000 for Soul model")
        if args.aspect_ratio not in SOUL_ASPECT_RATIOS:
            raise ValueError(
                f"Aspect ratio '{args.aspect_ratio}' not supported for Soul. "
                f"Supported: {', '.join(SOUL_ASPECT_RATIOS)}"
            )

        # Resolve style ID
        style_id = resolve_style_id(args)
        styles = get_soul_styles()
        style_name = styles.get(style_id, {}).get("name", style_id)

        logger.info("Submitting Higgsfield Soul model image job...")
        logger.info("  Style: %s (%s)", style_name, style_id)
        logger.info("  Resolution: %s, Aspect: %s, Batch: %d", args.resolution, args.aspect_ratio, args.batch_size)
        logger.info("  use_unlim: %s", args.use_unlim)

        job_set = await generate_image_soul(
            prompt=args.prompt,
            aspect_ratio=args.aspect_ratio,
            style_id=style_id,
            style_strength=args.style_strength,
            seed=args.seed,
            resolution=args.resolution,
            steps=args.steps,
            sample_shift=args.sample_shift,
            sample_guide_scale=args.sample_guide_scale,
            negative_prompt=args.negative_prompt,
            enhance_prompt=args.enhance_prompt,
            use_unlim=args.use_unlim,
            batch_size=args.batch_size,
            account=account,
        )
    else:
        # Standard model generation
        if args.aspect_ratio not in STANDARD_ASPECT_RATIOS:
            raise ValueError(
                f"Aspect ratio '{args.aspect_ratio}' not supported for standard models. "
                f"Supported: {', '.join(STANDARD_ASPECT_RATIOS)}"
            )

        # Upload input images if provided
        input_images: List[Dict[str, str]] = []
        if args.input_images:
            logger.info("Uploading %d input image(s)...", len(args.input_images))
            input_images = await upload_input_images(args.input_images, account)

        logger.info("Submitting Higgsfield image job...")
        logger.info("  Model: %s, Aspect: %s", args.model, args.aspect_ratio)
        if input_images:
            logger.info("  Input images: %d", len(input_images))
        logger.info("  use_unlim: %s", args.use_unlim)

        # Use direct API call when input images are provided (or always for consistency)
        job_set = await generate_image_standard(
            prompt=args.prompt,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            guidance_scale=args.guidance_scale,
            seed=args.seed,
            use_unlim=args.use_unlim,
            input_images=input_images,
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
        logger.info("Found %d downloadable assets (png/webp).", len(downloadable_urls))
    else:
        logger.warning("No png/webp URLs reported; downloading all available URLs instead.")
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
        logger.error("Failed to generate image: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
