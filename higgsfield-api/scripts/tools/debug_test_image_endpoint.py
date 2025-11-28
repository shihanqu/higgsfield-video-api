#!/usr/bin/env python3
"""
Probe the Higgsfield text-to-image endpoint described in API_REFERENCE.md.

The reference documents a POST request to https://fnf.higgsfield.ai/jobs/{model-name}
with a payload nested under the "params" key. This script builds that payload,
submits it to the chosen model, and prints the response so we can confirm the endpoint
behavior without digging through proxy logs.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
APP_ROOT = SCRIPTS_DIR.parent

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.repository.core import init_db
from src.services.higgsfield import get_last_used_account, get_token

# Default model used when --model is not specified
DEFAULT_MODEL = "nano_banana_2"

AVAILABLE_MODELS: List[str] = [
    "text2image_soul",
    "text2image",
    "text2image_gpt",
    "flux_kontext",
    "canvas",
    "canvas_soul",
    "wan2_2_image",
    "seedream",
    "nano_banana",
    "nano_banana_animal",
    "keyframes_faceswap",
    "reve",
    "nano_banana_2",
    "qwen_camera_control",
    "viral_transform_image",
    "flux_2",
    "game_dump",
]


def _build_model_lookup() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for name in AVAILABLE_MODELS:
        slug = name.replace("_", "-")
        mapping[name.lower()] = slug
        mapping[slug.lower()] = slug
    return mapping


MODEL_SLUG_LOOKUP = _build_model_lookup()


def resolve_model_slug(model_name: str) -> str:
    """Normalize user input (underscores vs hyphens) to an endpoint slug."""
    normalized = model_name.strip().lower()
    slug = MODEL_SLUG_LOOKUP.get(normalized)
    if slug:
        return slug
    raise ValueError(
        f"Unknown model '{model_name}'. Known models per API reference: "
        f"{', '.join(AVAILABLE_MODELS)}"
    )


def print_available_models() -> None:
    print("Available models from API_REFERENCE.md (slug in parentheses when different):")
    for name in AVAILABLE_MODELS:
        slug = name.replace("_", "-")
        if slug == name:
            print(f"- {name}")
        else:
            print(f"- {name} ({slug})")


def build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    """Construct the JSON body documented in API_REFERENCE.md."""
    return {
        "params": {
            "prompt": args.prompt,
            "input_images": [],
            "width": args.width,
            "height": args.height,
            "batch_size": args.batch_size,
            "aspect_ratio": args.aspect_ratio,
            "use_unlim": args.use_unlim,
            "resolution": args.resolution,
        },
        "use_unlim": args.use_unlim,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a diagnostic Higgsfield text-to-image request in line with API_REFERENCE.md."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        metavar="MODEL",
        help="Model identifier from API_REFERENCE.md (underscores or hyphens are accepted).",
    )
    parser.add_argument(
        "--prompt",
        default="A beautiful landscape at sunset",
        help="Prompt to send in the params payload.",
    )
    parser.add_argument("--width", type=int, default=1024, help="Image width in pixels.")
    parser.add_argument("--height", type=int, default=1024, help="Image height in pixels.")
    parser.add_argument(
        "--aspect-ratio",
        default="1:1",
        metavar="RATIO",
        help="Aspect ratio string passed through to the API.",
    )
    parser.add_argument(
        "--resolution",
        default="2k",
        help="Resolution preset recognized by Higgsfield (see API reference).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Number of images to request in a single job.",
    )
    parser.add_argument(
        "--use-unlim",
        dest="use_unlim",
        action="store_true",
        help="Set use_unlim=true in both the params object and the top-level payload.",
    )
    parser.add_argument(
        "--no-use-unlim",
        dest="use_unlim",
        action="store_false",
        help="Set use_unlim=false.",
    )
    parser.set_defaults(use_unlim=True)
    parser.add_argument(
        "--method",
        choices=("POST", "OPTIONS"),
        default="POST",
        help="HTTP method to use when probing the endpoint.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP client timeout in seconds.",
    )
    parser.add_argument(
        "--print-payload",
        action="store_true",
        help="Log the JSON payload before issuing the request (POST only).",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Print the models documented in API_REFERENCE.md and exit.",
    )
    args = parser.parse_args()

    if args.list_models:
        print_available_models()
        parser.exit()

    if args.width <= 0 or args.height <= 0:
        parser.error("Width and height must be positive integers.")
    if args.batch_size <= 0:
        parser.error("Batch size must be a positive integer.")

    try:
        args.model_slug = resolve_model_slug(args.model)
    except ValueError as exc:
        parser.error(str(exc))

    args.method = args.method.upper()
    return args


async def async_main(args: argparse.Namespace) -> None:
    await init_db()
    account = await get_last_used_account()
    if not account:
        raise RuntimeError("No active Higgsfield accounts found.")

    token = await get_token(account)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://fnf.higgsfield.ai/jobs/{args.model_slug}"
    print(f"Resolved endpoint: {url}")

    payload = None
    if args.method == "POST":
        payload = build_payload(args)
        if args.print_payload:
            print("Request payload:")
            print(json.dumps(payload, indent=2))

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        if args.method == "OPTIONS":
            response = await client.options(url, headers=headers)
        else:
            response = await client.post(url, headers=headers, json=payload)

    print(f"Status: {response.status_code}")
    allow_header = response.headers.get("allow")
    if allow_header:
        print("Allow:", allow_header)

    content_type = (response.headers.get("content-type") or "").lower()
    if "json" in content_type:
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"Failed to decode JSON response: {exc}")
            print("Raw body:", response.text)
            return

        print("JSON response:")
        print(json.dumps(body, indent=2))

        job_sets = body.get("job_sets")
        if isinstance(job_sets, list) and job_sets:
            job_id = job_sets[0].get("id")
            if job_id:
                print(f"First job_set ID: {job_id}")
    else:
        body_text = response.text.strip()
        if body_text:
            print("Body:", body_text)


def main():
    args = parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("Cancelled by user.")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to probe endpoint: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

