#!/usr/bin/env python3
import base64
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
from PIL import Image
# Note: playwright.sync_api is imported inside _refresh_account_auth_sync to avoid startup issues

from config import APP_ORIGIN, CLERK_APIVER, CLERK_BASE, CLERK_JSVER
from src.utils.exceptions import (
    APIRequestError,
    AuthStorageError,
    CookieParsingError,
    FileUploadError,
    ImageGenerationError,
    MotionConfigError,
    SessionError,
    TokenMintError,
    VideoGenerationError,
)

from ..repository.models.account import HiggsfieldAccount

logger = logging.getLogger("higgsfield")

MOTION_ID_PARAMS = {
    "GENERAL": {
        "id": "d2389a9a-91c2-4276-bc9c-c9e35e8fb85a",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/411820b9-2387-4958-99cc-699c757fcf9c.webp",
    },
    "DISINTEGRATION": {
        "id": "4e981984-1cdc-4b96-a2b1-1a7c1ecb822d",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/634ede39-bc1f-4635-b4bc-eee2d87a4735.webp",
    },
    "EARTH_ZOOM_OUT": {
        "id": "70e490b9-26b7-4572-8d9c-2ac8dcc9adc0",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/60fe4cdc-9baf-4616-a86c-0b0a51b012d8.webp",
    },
    "EYES_IN": {
        "id": "0ab33462-481e-4c78-8ffc-086bebd84187",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/1493b264-13b4-41e8-906c-b6405f9c1f0d.webp",
    },
    "FACE_PUNCH": {
        "id": "cd5bfd11-5a1a-46e0-9294-b22b0b733b1e",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/4c75250f-a508-4d36-b092-25cc0837f127.webp",
    },
    "ARC_RIGHT": {
        "id": "0bdbf318-f918-4f9b-829a-74cab681d806",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/f97e1093-b61a-4bbd-abed-4318fc1249e8.webp",
    },
    "HANDHELD": {
        "id": "36e6e450-52d9-484f-bfbe-f069e06a1530",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/2785cca1-c4bc-498f-bdd9-ce0012e8477b.webp",
    },
    "BUILDING_EXPLOSION": {
        "id": "e974bca9-c9eb-4cc8-9318-5676cc110f17",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/51d42294-6d2f-4e0c-8448-c3b8d4114292.webp",
    },
    "STATIC": {
        "id": "aab8440c-0d65-4554-b88a-7a9a5e084b6e",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/b9ee21e0-fa8a-4874-be6d-00f9763a9920.webp",
    },
    "TURNING_METAL": {
        "id": "46e23a6b-1047-40f1-9cf5-33f5f55ddf2e",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/d44a136d-8b78-49c8-bf3d-889e5f30c547.webp",
    },
    "3D_ROTATION": {
        "id": "6f06f47e-922e-4660-9fe9-754e4be69696",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/96ccaa14-59c4-49df-a91d-aa898794b32d.webp",
    },
    "SNORRICAM": {
        "id": "893cb65f-c528-40aa-83d8-c5aeb2bfe59f",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/11c848b3-c8dd-456f-a6dd-8c17e35eb7d0.webp",
    },
}

# ms = [{'id': '4e981984-1cdc-4b96-a2b1-1a7c1ecb822d',
#    'name': 'Disintegration',
#    'media': {'width': 320,
#     'height': 416,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/634ede39-bc1f-4635-b4bc-eee2d87a4735.webp',
#     'type': 'animated'},
#    'priority': -346,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['vfx', 'trending'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': '70e490b9-26b7-4572-8d9c-2ac8dcc9adc0',
#    'name': 'Earth Zoom Out',
#    'media': {'width': 320,
#     'height': 486,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/60fe4cdc-9baf-4616-a86c-0b0a51b012d8.webp',
#     'type': 'animated'},
#    'priority': -319,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': [],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': '0ab33462-481e-4c78-8ffc-086bebd84187',
#    'name': 'Eyes In',
#    'media': {'width': 320,
#     'height': 562,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/1493b264-13b4-41e8-906c-b6405f9c1f0d.webp',
#     'type': 'animated'},
#    'priority': -316,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['vfx', 'epic_camera_control'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': 'cd5bfd11-5a1a-46e0-9294-b22b0b733b1e',
#    'name': 'Face Punch',
#    'media': {'width': 320,
#     'height': 242,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/4c75250f-a508-4d36-b092-25cc0837f127.webp',
#     'type': 'animated'},
#    'priority': -308,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['vfx', 'trending'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': '0bdbf318-f918-4f9b-829a-74cab681d806',
#    'name': 'Arc Right',
#    'media': {'width': 320,
#     'height': 424,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/f97e1093-b61a-4bbd-abed-4318fc1249e8.webp',
#     'type': 'animated'},
#    'priority': -293,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['epic_camera_control', 'trending'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': '36e6e450-52d9-484f-bfbe-f069e06a1530',
#    'name': 'Handheld',
#    'media': {'width': 320,
#     'height': 320,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/2785cca1-c4bc-498f-bdd9-ce0012e8477b.webp',
#     'type': 'animated'},
#    'priority': -288,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['basic_camera_control', 'trending'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': 'e974bca9-c9eb-4cc8-9318-5676cc110f17',
#    'name': 'Building Explosion',
#    'media': {'width': 320,
#     'height': 568,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/51d42294-6d2f-4e0c-8448-c3b8d4114292.webp',
#     'type': 'animated'},
#    'priority': -281,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['vfx'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': 'aab8440c-0d65-4554-b88a-7a9a5e084b6e',
#    'name': 'Static',
#    'media': {'width': 320,
#     'height': 486,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/b9ee21e0-fa8a-4874-be6d-00f9763a9920.webp',
#     'type': 'animated'},
#    'priority': -277,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['basic_camera_control'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': '46e23a6b-1047-40f1-9cf5-33f5f55ddf2e',
#    'name': 'Turning Metal',
#    'media': {'width': 320,
#     'height': 424,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/d44a136d-8b78-49c8-bf3d-889e5f30c547.webp',
#     'type': 'animated'},
#    'priority': -275,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['vfx', 'new'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': '6f06f47e-922e-4660-9fe9-754e4be69696',
#    'name': '3D Rotation',
#    'media': {'width': 320,
#     'height': 320,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/96ccaa14-59c4-49df-a91d-aa898794b32d.webp',
#     'type': 'animated'},
#    'priority': -264,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': [],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': '893cb65f-c528-40aa-83d8-c5aeb2bfe59f',
#    'name': 'Snorricam',
#    'media': {'width': 320,
#     'height': 274,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/11c848b3-c8dd-456f-a6dd-8c17e35eb7d0.webp',
#     'type': 'animated'},
#    'priority': -263,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['epic_camera_control', 'trending'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}},
#   {'id': 'd2389a9a-91c2-4276-bc9c-c9e35e8fb85a',
#    'name': 'General',
#    'media': {'width': 320,
#     'height': 180,
#     'url': 'https://d1xarpci4ikg0w.cloudfront.net/411820b9-2387-4958-99cc-699c757fcf9c.webp',
#     'type': 'animated'},
#    'priority': -262,
#    'tags': ['top_choice'],
#    'preset_family': 'higgsfield',
#    'cms_id': None,
#    'categories': ['basic_camera_control', 'trending'],
#    'params': {'steps': 20, 'frames': 81, 'strength': 1.0, 'guide_scale': 6.0}}]


FRAME_MAPPING = {
    "3": 49,
    "5": 81,
}


def load_cookiejar(storage_path: Path) -> httpx.Cookies:
    """Load cookies from auth storage file.

    Args:
        storage_path: Path to the auth.json file

    Returns:
        httpx.Cookies: Loaded cookies

    Raises:
        AuthStorageError: If auth file doesn't exist or is invalid
        CookieParsingError: If cookie parsing fails
    """
    try:
        if not storage_path.exists():
            logger.error(f"Auth file not found at {storage_path}")
            raise AuthStorageError(f"Auth file not found at {storage_path}")

        try:
            state = json.loads(storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Invalid auth file format: {e}")
            raise AuthStorageError(f"Invalid auth file format: {e}")

        jar = httpx.Cookies()
        cookies = state.get("cookies", [])

        if not isinstance(cookies, list):
            logger.error("Invalid cookies format in auth file")
            raise AuthStorageError("Invalid cookies format in auth file")

        for c in cookies:
            try:
                # Keep all cookies for higgsfield.ai and clerk.higgsfield.ai (and subdomains)
                dom = c.get("domain", "")
                if "higgsfield.ai" in dom:
                    jar.set(c["name"], c["value"], domain=dom, path=c.get("path", "/"))
            except Exception as e:
                logger.warning(f"Failed to set cookie {c.get('name', 'unknown')}: {e}")
                continue

        return jar
    except Exception as e:
        logger.error(f"Failed to load cookies from auth file: {e}")
        raise AuthStorageError(f"Failed to load cookies from auth file: {e}")


def load_cookiejar_from_account(account: HiggsfieldAccount) -> httpx.Cookies:
    """Load cookies from account's cookies_json field.

    Args:
        account: HiggsfieldAccount instance with cookies_json

    Returns:
        httpx.Cookies: Loaded cookies

    Raises:
        AuthStorageError: If account cookies are invalid
    """
    try:
        jar = httpx.Cookies()
        cookies = account.cookies_json

        if not isinstance(cookies, list):
            logger.error("Invalid cookies format in account")
            raise AuthStorageError("Invalid cookies format in account")

        for c in cookies:
            try:
                # Keep all cookies for higgsfield.ai and clerk.higgsfield.ai (and subdomains)
                dom = c.get("domain", "")
                if "higgsfield.ai" in dom:
                    jar.set(c["name"], c["value"], domain=dom, path=c.get("path", "/"))
            except Exception as e:
                logger.warning(f"Failed to set cookie {c.get('name', 'unknown')}: {e}")
                continue

        return jar
    except Exception as e:
        logger.error(f"Failed to load cookies from account: {e}")
        raise AuthStorageError(f"Failed to load cookies from account: {e}")


def get_cookie(
    jar: httpx.Cookies, name: str, domain_contains: Optional[str] = None
) -> Optional[str]:
    """Extract a specific cookie value from the cookie jar.

    Args:
        jar: httpx.Cookies object
        name: Cookie name to search for
        domain_contains: Optional domain filter

    Returns:
        Cookie value if found, None otherwise

    Raises:
        CookieParsingError: If cookie access fails
    """
    try:
        for c in jar.jar:
            if c.name == name and (
                domain_contains is None or domain_contains in c.domain
            ):
                return c.value
        return None
    except Exception as e:
        raise CookieParsingError(f"Failed to access cookie '{name}': {e}")


def b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def try_session_id_from_clerk_active_context(jar: httpx.Cookies) -> Optional[str]:
    """Try to extract session ID from clerk_active_context cookie.

    Args:
        jar: Cookie jar to search

    Returns:
        Session ID if found, None otherwise
    """
    try:
        # cookie looks like: "sess_ABC123:..."
        v = get_cookie(jar, "clerk_active_context", "higgsfield.ai")
        if not v:
            return None
        sid = v.split(":", 1)[0].strip()
        return sid if sid.startswith("sess_") else None
    except Exception as e:
        logger.warning(f"Failed to parse clerk_active_context cookie: {e}")
        return None


def try_session_id_from___session_jwt(jar: httpx.Cookies) -> Optional[str]:
    """Try to extract session ID from __session JWT cookie.

    Args:
        jar: Cookie jar to search

    Returns:
        Session ID if found, None otherwise
    """
    # __session is a JWT; its payload has "sid": "sess_...".
    for name in ("__session", "__session_FQWayshe"):
        try:
            tok = get_cookie(jar, name, "higgsfield.ai")
            if not tok:
                continue

            parts = tok.split(".")
            if len(parts) < 2:
                logger.warning(f"Invalid JWT format in {name} cookie")
                continue

            payload = json.loads(b64url_decode(parts[1]).decode("utf-8"))
            sid = payload.get("sid")
            if isinstance(sid, str) and sid.startswith("sess_"):
                return sid

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to decode JWT from {name} cookie: {e}")
            continue
        except Exception as e:
            logger.warning(f"Unexpected error parsing {name} cookie: {e}")
            continue

    return None


async def get_session_id_via_api(client: httpx.AsyncClient) -> Optional[str]:
    """Get session ID via Clerk API as fallback method.

    Args:
        client: HTTP client with cookies

    Returns:
        Session ID if found, None otherwise

    Raises:
        SessionError: If API request fails or response is invalid
    """
    try:
        # Fallback: GET /v1/client and pick last_active_session_id or an active session
        url = f"{CLERK_BASE}/v1/client"
        params = {"__clerk_api_version": CLERK_APIVER, "_clerk_js_version": CLERK_JSVER}
        headers = {
            "Accept": "application/json",
            "Origin": APP_ORIGIN,
            "Referer": f"{APP_ORIGIN}/",
        }

        r = await client.get(url, params=params, headers=headers, timeout=120)
        r.raise_for_status()

        try:
            j = r.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Clerk API: {e}")
            raise SessionError(f"Invalid JSON response from Clerk API: {e}")

        client_data = None
        if isinstance(j, dict):
            client_data = j.get("client") or j
        elif isinstance(j, list) and j:
            first_item = j[0]
            if isinstance(first_item, dict):
                client_data = first_item.get("client") or first_item

        if not isinstance(client_data, dict):
            logger.error("Invalid client data format in API response: %s", j)
            raise SessionError("Invalid client data format in API response")

        # Try last active session first
        sid = client_data.get("last_active_session_id")
        if sid:
            return sid

        # Try active sessions
        sessions = client_data.get("sessions") or []
        for s in sessions:
            if s.get("status") == "active" and isinstance(s.get("id"), str):
                return s["id"]

        # Fallback to any session
        if sessions:
            first_session_id = sessions[0].get("id")
            if isinstance(first_session_id, str):
                return first_session_id

        return None

    except httpx.HTTPStatusError as e:
        raise SessionError(
            f"Clerk API request failed with status {e.response.status_code}: {e}"
        )
    except httpx.RequestError as e:
        raise SessionError(f"Network error during Clerk API request: {e}")
    except Exception as e:
        raise SessionError(f"Unexpected error getting session ID via API: {e}")


async def mint_session_token(client: httpx.AsyncClient, session_id: str) -> str:
    """Mint a session token from Clerk API.

    Args:
        client: HTTP client with cookies
        session_id: Session ID to mint token for

    Returns:
        Session token

    Raises:
        TokenMintError: If token minting fails
    """
    try:
        url = f"{CLERK_BASE}/v1/client/sessions/{session_id}/tokens"
        params = {"__clerk_api_version": CLERK_APIVER, "_clerk_js_version": CLERK_JSVER}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
            "Origin": APP_ORIGIN,
            "Referer": f"{APP_ORIGIN}/",
        }

        # Try without any form data - Clerk API doesn't accept action parameter
        r = await client.post(url, params=params, headers=headers, timeout=120)
        r.raise_for_status()

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            raise TokenMintError(f"Invalid JSON response from token mint API: {e}")

        # Look for token in various possible fields
        for key in ("jwt", "token", "client_jwt", "session_token"):
            if key in data and isinstance(data[key], str) and data[key]:
                return data[key]

        raise TokenMintError(
            f"No valid token found in response. Available keys: {list(data.keys())}"
        )

    except httpx.HTTPStatusError as e:
        raise TokenMintError(
            f"Token mint request failed with status {e.response.status_code}: {e}"
        )
    except httpx.RequestError as e:
        raise TokenMintError(f"Network error during token mint: {e}")
    except TokenMintError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error minting token: {e}")
        raise TokenMintError(f"Unexpected error minting token: {e}")


async def get_token(account: HiggsfieldAccount) -> str:
    """Get authentication token for Higgsfield API.

    Args:
        account: HiggsfieldAccount instance containing cookies_json

    Returns:
        Authentication token

    Raises:
        AuthStorageError: If account cookies are invalid
        SessionError: If session management fails
        TokenMintError: If token minting fails
    """
    try:
        jar = load_cookiejar_from_account(account)
    except Exception as e:
        logger.error(f"Failed to load authentication cookies from account: {e}")
        raise AuthStorageError(
            f"Failed to load authentication cookies from account: {e}"
        )

    # Optional: look a bit more like a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/141.0"
    }

    try:
        async with httpx.AsyncClient(cookies=jar, headers=headers) as client:
            # 1) Fast path: cookie value
            sid = try_session_id_from_clerk_active_context(jar)

            # 2) Fallback: decode __session JWT
            if not sid:
                sid = try_session_id_from___session_jwt(jar)

            # 3) Fallback: GET /v1/client
            if not sid:
                try:
                    sid = await get_session_id_via_api(client)
                except SessionError as e:
                    logger.error(f"Failed to get session ID via API: {e}")
                    raise

            if not sid:
                raise SessionError(
                    "Could not determine Clerk session ID. Please refresh your auth.json file."
                )

            try:
                token = await mint_session_token(client, sid)
                return token
            except TokenMintError as e:
                logger.error(f"Token minting failed: {e}")
                raise

    except (SessionError, TokenMintError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token acquisition: {e}")
        raise SessionError(f"Unexpected error during token acquisition: {e}")


async def get_job_set_id(job_set_id: str, account: HiggsfieldAccount) -> Dict[str, Any]:
    """Get job set information by ID.

    Args:
        job_set_id: ID of the job set to retrieve
        account: HiggsfieldAccount instance for authentication

    Returns:
        Job set data

    Raises:
        APIRequestError: If the API request fails
        ValueError: If job_set_id is invalid
    """
    if not job_set_id or not job_set_id.strip():
        logger.error("job_set_id cannot be empty")
        raise ValueError("job_set_id cannot be empty")

    try:
        token = await get_token(account)

        async with httpx.AsyncClient() as client:
            url = f"https://fnf.higgsfield.ai/job-sets/{job_set_id}"
            headers = {"Authorization": f"Bearer {token}"}

            res = await client.get(url, headers=headers, timeout=120)
            res.raise_for_status()

            try:
                data = res.json()
                logger.info(f"Successfully retrieved job set {job_set_id}")
                return data
            except json.JSONDecodeError as e:
                raise APIRequestError(
                    f"Invalid JSON response from job set API: {e}", res.status_code
                )

    except httpx.HTTPStatusError as e:
        raise APIRequestError(
            f"Job set API request failed: {e}",
            e.response.status_code,
            e.response.text if hasattr(e.response, "text") else None,
        )
    except httpx.RequestError as e:
        raise APIRequestError(f"Network error during job set request: {e}")
    except (SessionError, TokenMintError, AuthStorageError):
        raise
    except Exception as e:
        raise APIRequestError(f"Unexpected error getting job set: {e}")


async def get_motions(
    account: HiggsfieldAccount, size: int = 30, preset_family: str = "higgsfield"
) -> Dict[str, Any]:
    """Get available motion presets.

    Args:
        account: HiggsfieldAccount instance for authentication
        size: Number of motions to retrieve (default: 30)
        preset_family: Preset family name (default: "higgsfield")

    Returns:
        Motion presets data

    Raises:
        APIRequestError: If the API request fails
        ValueError: If parameters are invalid
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if not preset_family or not preset_family.strip():
        raise ValueError("preset_family cannot be empty")

    try:
        token = await get_token(account)

        async with httpx.AsyncClient() as client:
            url = "https://fnf.higgsfield.ai/motions"
            params = {"size": size, "search": "", "preset_family": preset_family}
            headers = {"Authorization": f"Bearer {token}"}

            res = await client.get(url, params=params, headers=headers, timeout=120)
            res.raise_for_status()

            try:
                data = res.json()
                logger.info(
                    f"Successfully retrieved {len(data.get('items', []))} motions"
                )
                return data
            except json.JSONDecodeError as e:
                raise APIRequestError(
                    f"Invalid JSON response from motions API: {e}", res.status_code
                )

    except httpx.HTTPStatusError as e:
        raise APIRequestError(
            f"Motions API request failed: {e}",
            e.response.status_code,
            e.response.text if hasattr(e.response, "text") else None,
        )
    except httpx.RequestError as e:
        raise APIRequestError(f"Network error during motions request: {e}")
    except (SessionError, TokenMintError, AuthStorageError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting motions: {e}")
        raise APIRequestError(f"Unexpected error getting motions: {e}")


async def get_upload_url(account: HiggsfieldAccount) -> Dict[str, Any]:
    """Get upload URL for media files.

    Args:
        account: HiggsfieldAccount instance for authentication

    Returns:
        Upload URL data including upload_url, id, url, and content_type

    Raises:
        APIRequestError: If the API request fails
    """
    try:
        token = await get_token(account)

        async with httpx.AsyncClient() as client:
            url = "https://fnf.higgsfield.ai/media"
            headers = {"Authorization": f"Bearer {token}"}

            res = await client.post(url, headers=headers, timeout=120)
            res.raise_for_status()

            try:
                data = res.json()

                # Validate required fields
                required_fields = ["upload_url", "id", "url", "content_type"]
                missing_fields = [
                    field for field in required_fields if field not in data
                ]
                if missing_fields:
                    raise APIRequestError(
                        f"Upload URL response missing fields: {missing_fields}"
                    )

                logger.info(
                    f"Successfully obtained upload URL for media ID: {data.get('id')}"
                )
                return data

            except json.JSONDecodeError as e:
                raise APIRequestError(
                    f"Invalid JSON response from upload URL API: {e}", res.status_code
                )

    except httpx.HTTPStatusError as e:
        raise APIRequestError(
            f"Upload URL API request failed: {e}",
            e.response.status_code,
            e.response.text if hasattr(e.response, "text") else None,
        )
    except httpx.RequestError as e:
        raise APIRequestError(f"Network error during upload URL request: {e}")
    except (SessionError, TokenMintError, AuthStorageError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting upload URL: {e}")
        raise APIRequestError(f"Unexpected error getting upload URL: {e}")


async def submit_upload(id: str, account: HiggsfieldAccount) -> None:
    """Submit upload completion notification.

    Args:
        id: Media ID to mark as uploaded
        account: HiggsfieldAccount instance for authentication

    Raises:
        APIRequestError: If the API request fails
        ValueError: If id is invalid
    """
    if not id or not id.strip():
        raise ValueError("Media ID cannot be empty")

    try:
        token = await get_token(account)

        async with httpx.AsyncClient() as client:
            url = f"https://fnf.higgsfield.ai/media/{id}/upload"
            headers = {"Authorization": f"Bearer {token}"}

            res = await client.post(url, headers=headers, timeout=120)
            res.raise_for_status()

            logger.info(f"Successfully submitted upload for media ID: {id}")

    except httpx.HTTPStatusError as e:
        raise APIRequestError(
            f"Submit upload API request failed: {e}",
            e.response.status_code,
            e.response.text if hasattr(e.response, "text") else None,
        )
    except httpx.RequestError as e:
        raise APIRequestError(f"Network error during submit upload request: {e}")
    except (SessionError, TokenMintError, AuthStorageError):
        raise
    except Exception as e:
        raise APIRequestError(f"Unexpected error submitting upload: {e}")


async def upload_image(image_path: str, account: HiggsfieldAccount) -> Dict[str, str]:
    """Upload an image file to Higgsfield storage.

    Args:
        image_path: Path to the image file to upload
        account: HiggsfieldAccount instance for authentication

    Returns:
        Dictionary with id, url, and type of uploaded image

    Raises:
        FileUploadError: If file upload fails
        ValueError: If image_path is invalid
        FileNotFoundError: If image file doesn't exist
    """
    if not image_path or not image_path.strip():
        raise ValueError("image_path cannot be empty")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    if not image_path.is_file():
        raise ValueError(f"Path is not a file: {image_path}")

    try:
        # Get upload URL
        upload_data = await get_upload_url(account)
        upload_url = upload_data.get("upload_url")
        media_id = upload_data.get("id")
        url = upload_data.get("url")
        content_type = upload_data.get("content_type")

        img = Image.open(image_path)
        width, height = img.size

        # Upload the file
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                with open(image_path, "rb") as f:
                    file_content = f.read()

                if not file_content:
                    raise FileUploadError(f"Image file is empty: {image_path}")

                res = await client.put(
                    upload_url,
                    content=file_content,
                    headers={"Content-Type": content_type},
                    timeout=120,
                )
                res.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise FileUploadError(
                f"Image upload failed with status {e.response.status_code}: {e}"
            )
        except httpx.RequestError as e:
            raise FileUploadError(f"Network error during image upload: {e}")
        except IOError as e:
            raise FileUploadError(f"File read error: {e}")

        # Submit upload completion
        try:
            await submit_upload(media_id, account)
        except APIRequestError as e:
            logger.warning(
                f"Upload completion notification failed, but image may still be uploaded: {e}"
            )
            # Don't raise here as the upload itself succeeded

        result = {
            "id": media_id,
            "url": url,
            "type": content_type,
            "width": width,
            "height": height,
        }
        logger.info(f"Successfully uploaded image {image_path} with ID: {media_id}")
        return result

    except (FileUploadError, ValueError, FileNotFoundError):
        raise
    except (APIRequestError, SessionError, TokenMintError, AuthStorageError) as e:
        raise FileUploadError(f"Upload preparation failed: {e}")
    except Exception as e:
        raise FileUploadError(f"Unexpected error during image upload: {e}")


async def generate_video(
    prompt: str,
    image_path: str,
    motion: str,
    model: str,
    duration: str,
    account: HiggsfieldAccount,
) -> Dict[str, Any]:
    """Generate a video from an image and prompt.

    Args:
        prompt: Text prompt for video generation
        image_path: Path to the input image file
        motion: Motion preset ID
        model: Model to use for generation
        duration: Duration of the video
        account: HiggsfieldAccount instance for authentication

    Returns:
        Video generation job data

    Raises:
        VideoGenerationError: If video generation fails
        MotionConfigError: If motion configuration is invalid
        ValueError: If parameters are invalid
    """

    try:
        # Upload the image
        try:
            image_data = await upload_image(image_path, account)
        except (FileUploadError, FileNotFoundError, ValueError) as e:
            raise VideoGenerationError(f"Image upload failed: {e}")

        # Get motion configuration
        motion_params = MOTION_ID_PARAMS.get(motion)
        if not motion_params:
            available_motions = list(MOTION_ID_PARAMS.keys())
            raise MotionConfigError(
                f"Motion ID '{motion}' not found. Available motions: {available_motions}"
            )

        try:
            frames = FRAME_MAPPING.get(duration)
            if not frames or not isinstance(frames, int) or frames <= 0:
                raise MotionConfigError(
                    f"Invalid frames configuration for motion {motion}"
                )
        except (AttributeError, TypeError) as e:
            raise MotionConfigError(f"Invalid motion parameters structure: {e}")

        # Build payload
        payload = {
            "params": {
                "prompt": prompt,
                "enhance_prompt": True,
                "model": model,
                "frames": frames,
                "input_image": {
                    "id": image_data.get("id"),
                    "url": image_data.get("url"),
                    "type": "media_input",
                },
                "motion_id": motion_params.get("id"),
                "width": image_data.get("width"),
                "height": image_data.get("height"),
                "seed": random.randint(1, 1000000),
                "steps": 30,
            }
        }
        # Submit video generation job
        try:
            token = await get_token(account)

            async with httpx.AsyncClient(timeout=120) as client:
                url = "https://fnf.higgsfield.ai/jobs/image2video"
                headers = {"Authorization": f"Bearer {token}"}

                res = await client.post(url, headers=headers, json=payload)
                res.raise_for_status()

                try:
                    data = res.json()
                    logger.info(
                        f"Successfully submitted video generation job. Job ID: {data.get('job_sets', [])}"
                    )
                    return data
                except json.JSONDecodeError as e:
                    raise VideoGenerationError(
                        f"Invalid JSON response from video generation API: {e}"
                    )

        except httpx.HTTPStatusError as e:
            raise VideoGenerationError(
                f"Video generation API request failed with status {e.response.status_code}: {e}"
            )
        except httpx.RequestError as e:
            raise VideoGenerationError(
                f"Network error during video generation request: {e}"
            )

    except (VideoGenerationError, MotionConfigError, ValueError):
        raise
    except (SessionError, TokenMintError, AuthStorageError) as e:
        raise VideoGenerationError(f"Authentication failed: {e}")
    except Exception as e:
        raise VideoGenerationError(f"Unexpected error during video generation: {e}")


async def generate_image(
    prompt: str,
    model: str,
    aspect_ratio: str,
    guidance_scale: float,
    seed: Optional[int],
    account: HiggsfieldAccount,
    use_unlim: bool = True,
) -> Dict[str, Any]:
    """Generate an image from a text prompt."""

    MODEL_ENDPOINTS = {
        "lite": "nano-banana-2",
        "standard": "flux-2",
        "turbo": "seedream",
        "text2image": "text2image",
        "text2image_soul": "text2image-soul",
        "text2image-soul": "text2image-soul",
        "text2image_gpt": "text2image-gpt",
        "text2image-gpt": "text2image-gpt",
        "flux_kontext": "flux-kontext",
        "flux-kontext": "flux-kontext",
        "canvas": "canvas",
        "canvas_soul": "canvas-soul",
        "canvas-soul": "canvas-soul",
        "wan2_2_image": "wan2-2-image",
        "wan2-2-image": "wan2-2-image",
        "seedream": "seedream",
        "nano_banana": "nano-banana",
        "nano-banana": "nano-banana",
        "nano_banana_animal": "nano-banana-animal",
        "nano-banana-animal": "nano-banana-animal",
        "nano_banana_2": "nano-banana-2",
        "nano-banana-2": "nano-banana-2",
        "keyframes_faceswap": "keyframes-faceswap",
        "keyframes-faceswap": "keyframes-faceswap",
        "qwen_camera_control": "qwen-camera-control",
        "qwen-camera-control": "qwen-camera-control",
        "viral_transform_image": "viral-transform-image",
        "viral-transform-image": "viral-transform-image",
        "flux_2": "flux-2",
        "flux-2": "flux-2",
        "game_dump": "game-dump",
        "game-dump": "game-dump",
    }
    ASPECT_TO_DIMENSIONS: Dict[str, Tuple[int, int]] = {
        "1:1": (1024, 1024),
        "3:4": (896, 1152),
        "4:3": (1152, 896),
        "16:9": (1344, 768),
        "9:16": (768, 1344),
    }

    if not prompt or not prompt.strip():
        raise ImageGenerationError("Prompt cannot be empty")
    if not aspect_ratio or not isinstance(aspect_ratio, str):
        raise ImageGenerationError("Aspect ratio must be provided")

    dimensions = ASPECT_TO_DIMENSIONS.get(aspect_ratio)
    if not dimensions:
        raise ImageGenerationError(
            f"Unsupported aspect ratio '{aspect_ratio}'. "
            f"Supported values: {', '.join(ASPECT_TO_DIMENSIONS)}"
        )

    width, height = dimensions
    model_normalized = model.strip()
    model_key = model_normalized.lower()
    model_endpoint = MODEL_ENDPOINTS.get(model_key)
    if not model_endpoint:
        # Fall back to replacing underscores with hyphens, which matches most Higgsfield slugs
        model_endpoint = model_key.replace("_", "-")

    payload: Dict[str, Any] = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "width": width,
        "height": height,
        "batch_size": 1,
        "use_unlim": use_unlim,
        "resolution": "2k",
        "input_images": [],
        "enhance_prompt": True,
    }
    if seed is not None:
        payload["seed"] = seed

    try:
        token = await get_token(account)

        async with httpx.AsyncClient(timeout=120) as client:
            url = f"https://fnf.higgsfield.ai/jobs/{model_endpoint}"
            headers = {"Authorization": f"Bearer {token}"}
            res = await client.post(
                url,
                headers=headers,
                json={"params": payload, "use_unlim": use_unlim},
            )
            res.raise_for_status()

            try:
                data = res.json()
            except json.JSONDecodeError as e:
                raise ImageGenerationError(
                    f"Invalid JSON response from image generation API: {e}"
                )

            logger.info(
                "Successfully submitted image generation job. Job ID(s): %s",
                data.get("job_sets", []),
            )
            return data

    except httpx.HTTPStatusError as e:
        raise ImageGenerationError(
            f"Image generation API request failed with status {e.response.status_code}: {e}"
        )
    except httpx.RequestError as e:
        raise ImageGenerationError(f"Network error during image generation: {e}")
    except (SessionError, TokenMintError, AuthStorageError) as e:
        raise ImageGenerationError(f"Authentication failed: {e}")
    except Exception as e:
        raise ImageGenerationError(f"Unexpected error during image generation: {e}")


def _refresh_account_auth_sync(cookies_json: list, account_id: int) -> list:
    """
    Synchronous helper to refresh account auth using Playwright.
    
    This runs in a thread pool to avoid blocking the async event loop.
    Returns the new cookies list.
    """
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=BlockThirdPartyCookies",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
                "--use-mock-keychain",
            ],
        )

        # Load existing cookies into context
        context = browser.new_context(
            storage_state={"cookies": cookies_json}
        )
        page = context.new_page()

        logger.info("Opening Higgsfield with saved cookies...")
        page.goto("https://higgsfield.ai/create/video")

        current_url = page.url
        logger.info(f"Current URL: {current_url}")

        if "auth" in current_url:
            logger.warning("Still on auth page — session might be expired.")
        else:
            logger.info("Session restored successfully, user is logged in.")

        # Save the refreshed storage state
        temp_path = Path(f"{account_id}.json")
        page.context.storage_state(path=str(temp_path))
        logger.info(f"Saved refreshed auth state to {temp_path}")

        browser.close()
        
        new_auth = json.loads(temp_path.read_text())
        new_cookies = [
            c
            for c in new_auth.get("cookies", [])
            if "higgsfield.ai" in c.get("domain", "")
        ]
        temp_path.unlink()
        
        return new_cookies


async def refresh_account_auth(account: HiggsfieldAccount):
    """Load saved session cookies, visit Higgsfield, and save refreshed storage state."""
    import asyncio
    import concurrent.futures

    if not account.cookies_json:
        logger.error("No cookies provided for account %s", account.id)
        raise ValueError("No cookies provided")

    # Run sync Playwright in a thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        new_cookies = await loop.run_in_executor(
            pool,
            _refresh_account_auth_sync,
            account.cookies_json,
            account.id,
        )

    account.cookies_json = new_cookies
    account.last_updated_at = datetime.now(timezone.utc)
    await account.save()

    logger.info(f"Saved refreshed auth state for account {account.id}")


async def get_account_info(account: HiggsfieldAccount):
    """Get the balance of an account."""
    try:
        token = await get_token(account)
        async with httpx.AsyncClient(timeout=120) as client:
            url = "https://fnf.higgsfield.ai/user"
            headers = {"Authorization": f"Bearer {token}"}
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            return res.json()
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        raise APIRequestError(f"Error getting account info: {e}")


async def get_last_used_account():
    """Get the last used account."""
    accounts = await HiggsfieldAccount.filter(is_active=True).order_by("last_used_at")
    if not accounts:
        return None
    for account in accounts:
        account.last_used_at = datetime.now(timezone.utc)
        await account.save()
        return account


async def ensure_authenticated_account():
    """
    Ensure we have a valid authenticated Higgsfield account.
    
    If no account exists in the database but auth.json exists, it will
    automatically add the account from auth.json.
    
    Returns:
        HiggsfieldAccount: A valid, authenticated account
        
    Raises:
        RuntimeError: If no valid account or auth.json available
    """
    from environs import Env
    
    # First, try to get an existing account from database
    account = await get_last_used_account()
    
    if account:
        # Verify the account's token is still valid
        try:
            await get_token(account)
            logger.info("Using existing account: %s", account.username)
            return account
        except Exception as e:
            logger.warning("Existing account token invalid: %s", e)
            # Will try to re-add from auth.json below
    
    # No valid account in database - try to add from auth.json
    logger.info("No valid account in database. Checking for auth.json...")
    
    # Get paths
    app_root = Path(__file__).resolve().parent.parent.parent
    auth_json_path = app_root / "auth.json"
    
    if not auth_json_path.exists():
        raise RuntimeError(
            f"No auth.json found at {auth_json_path}. "
            "Please run 'python scripts/manage_accounts.py login' to authenticate."
        )
    
    # Load cookies from auth.json
    try:
        auth_data = json.loads(auth_json_path.read_text(encoding="utf-8"))
        cookies = auth_data.get("cookies", [])
        
        # Filter to Higgsfield cookies only
        hf_cookies = [c for c in cookies if "higgsfield.ai" in c.get("domain", "")]
        
        if not hf_cookies:
            raise RuntimeError(
                "auth.json exists but contains no Higgsfield cookies. "
                "Please run 'python scripts/manage_accounts.py login --force' to re-authenticate."
            )
        
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid auth.json format: {e}")
    
    # Get username from .env.credentials
    env = Env()
    for candidate in (
        app_root / ".env.credentials",
        app_root / ".env",
    ):
        if candidate.exists():
            env.read_env(candidate)
            break
    
    username = env.str("HIGGSFIELD_LOGIN_EMAIL", default="local@higgsfield.ai")
    
    # Add or update account in database
    existing_account = await HiggsfieldAccount.get_or_none(username=username)
    if existing_account:
        existing_account.cookies_json = hf_cookies
        existing_account.is_active = True
        existing_account.last_updated_at = datetime.now(timezone.utc)
        await existing_account.save()
        logger.info("Updated existing account: %s", username)
        account = existing_account
    else:
        account = await HiggsfieldAccount.create(
            username=username,
            cookies_json=hf_cookies,
            is_active=True,
        )
        logger.info("Created new account from auth.json: %s", username)
    
    # Verify the token works
    try:
        await get_token(account)
    except Exception as e:
        raise RuntimeError(
            f"auth.json credentials are invalid or expired: {e}. "
            "Please run 'python scripts/manage_accounts.py login --force' to re-authenticate."
        )
    
    logger.info("Successfully authenticated as: %s", account.username)
    return account
