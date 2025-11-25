#!/usr/bin/env python3
import base64
import json
import logging
import sys
from pathlib import Path

import requests

from config import APP_ORIGIN, CLERK_APIVER, CLERK_BASE, CLERK_JSVER, STORAGE

logger = logging.getLogger("higgsfield")

MOTION_ID_PARAMS = {
    "GENERAL": {
        "id": "d2389a9a-91c2-4276-bc9c-c9e35e8fb85a",
        "example": "https://d1xarpci4ikg0w.cloudfront.net/411820b9-2387-4958-99cc-699c757fcf9c.webp",
    },
}

FRAME_MAPPING = {
    "3": 49,
    "5": 81,
}


def load_cookiejar(storage_path: Path) -> requests.cookies.RequestsCookieJar:
    if not storage_path.exists():
        sys.stderr.write(f"[!] auth.json not found at {storage_path}\n")
        sys.exit(1)
    state = json.loads(storage_path.read_text(encoding="utf-8"))
    jar = requests.cookies.RequestsCookieJar()
    for c in state.get("cookies", []):
        # Keep all cookies for higgsfield.ai and clerk.higgsfield.ai (and subdomains)
        dom = c.get("domain", "")
        if "higgsfield.ai" in dom:
            jar.set(c["name"], c["value"], domain=dom, path=c.get("path", "/"))
    return jar


def get_cookie(
    jar: requests.cookies.RequestsCookieJar,
    name: str,
    domain_contains: str | None = None,
) -> str | None:
    for c in jar:
        if c.name == name and (domain_contains is None or domain_contains in c.domain):
            return c.value
    return None


def b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def try_session_id_from_clerk_active_context(jar) -> str | None:
    # cookie looks like: "sess_ABC123:..."
    v = get_cookie(jar, "clerk_active_context", "higgsfield.ai")
    if not v:
        return None
    sid = v.split(":", 1)[0].strip()
    return sid if sid.startswith("sess_") else None


def try_session_id_from___session_jwt(jar) -> str | None:
    # __session is a JWT; its payload has "sid": "sess_...".
    for name in ("__session", "__session_FQWayshe"):
        tok = get_cookie(jar, name, "higgsfield.ai")
        if not tok:
            continue
        try:
            parts = tok.split(".")
            if len(parts) < 2:
                continue
            payload = json.loads(b64url_decode(parts[1]).decode("utf-8"))
            sid = payload.get("sid")
            if isinstance(sid, str) and sid.startswith("sess_"):
                return sid
        except Exception:
            pass
    return None


def get_session_id_via_api(sess: requests.Session) -> str | None:
    # Fallback: GET /v1/client and pick last_active_session_id or an active session
    url = f"{CLERK_BASE}/v1/client"
    params = {"__clerk_api_version": CLERK_APIVER, "_clerk_js_version": CLERK_JSVER}
    headers = {
        "Accept": "application/json",
        "Origin": APP_ORIGIN,
        "Referer": f"{APP_ORIGIN}/",
    }
    r = sess.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    j = r.json()
    client = j.get("client", j)
    sid = client.get("last_active_session_id")
    if sid:
        return sid
    for s in client.get("sessions") or []:
        if s.get("status") == "active" and isinstance(s.get("id"), str):
            return s["id"]
    if client.get("sessions"):
        return client["sessions"][0].get("id")
    return None


def mint_session_token(sess: requests.Session, session_id: str) -> str:
    url = f"{CLERK_BASE}/v1/client/sessions/{session_id}/tokens"
    params = {"__clerk_api_version": CLERK_APIVER, "_clerk_js_version": CLERK_JSVER}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "Origin": APP_ORIGIN,
        "Referer": f"{APP_ORIGIN}/",
    }
    # Try without any form data - Clerk API doesn't accept action parameter
    r = sess.post(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    for key in ("jwt", "token", "client_jwt", "session_token"):
        if key in data and isinstance(data[key], str) and data[key]:
            return data[key]
    raise RuntimeError(f"Token not found in response: {data}")


def get_token():
    jar = load_cookiejar(Path(STORAGE))
    sess = requests.Session()
    sess.cookies.update(jar)
    # Optional: look a bit more like a browser
    sess.headers.update(
        {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/141.0"}
    )

    # 1) Fast path: cookie value
    sid = try_session_id_from_clerk_active_context(jar)
    # 2) Fallback: decode __session JWT
    if not sid:
        sid = try_session_id_from___session_jwt(jar)
    # 3) Fallback: GET /v1/client
    if not sid:
        try:
            sid = get_session_id_via_api(sess)
        except requests.HTTPError as e:
            sys.stderr.write(f"[!] Failed GET /v1/client: {e}\n")

    if not sid:
        sys.stderr.write(
            "[!] Could not determine Clerk session id. Refresh your auth.json.\n"
        )
        sys.exit(1)

    try:
        token = mint_session_token(sess, sid)
    except requests.HTTPError as e:
        sys.stderr.write(f"[!] Clerk token mint failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"[!] Unexpected response while minting token: {e}\n")
        sys.exit(1)

    return token


def get_job_set_id(job_set_id: str):
    token = get_token()
    res = requests.get(
        f"https://fnf.higgsfield.ai/job-sets/{job_set_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.json()


def get_motions(size: int = 30, preset_family: str = "higgsfield"):
    token = get_token()
    res = requests.get(
        f"https://fnf.higgsfield.ai/motions?size={size}&search=&preset_family={preset_family}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.json()


def get_upload_url():
    token = get_token()
    res = requests.post(
        "https://fnf.higgsfield.ai/media", headers={"Authorization": f"Bearer {token}"}
    )
    return res.json()


def submit_upload(id: str):
    token = get_token()
    requests.post(
        f"https://fnf.higgsfield.ai/media/{id}/upload",
        headers={"Authorization": f"Bearer {token}"},
    )


def upload_image(image_path: str):
    upload_data = get_upload_url()
    upload_url = upload_data.get("upload_url")
    id = upload_data.get("id")
    url = upload_data.get("url")
    content_type = upload_data.get("content_type")
    with open(image_path, "rb") as f:
        requests.put(
            upload_url,
            data=f,
            headers={"Content-Type": content_type},
            timeout=120,
        )

    submit_upload(id)
    return {"id": id, "url": url, "type": content_type}


def generate_video(
    prompt: str,
    image_path: str,
    motion: str,
    model: str,
    duration: str,
):
    image_data = upload_image(image_path)
    motion_params = MOTION_ID_PARAMS.get(motion)
    if not motion_params:
        raise ValueError(f"Motion ID {motion} not found")
    frames = FRAME_MAPPING.get(duration)
    if not frames or not isinstance(frames, int) or frames <= 0:
        raise ValueError(f"Invalid frames configuration for motion {motion}")
    payload = {
        "params": {
            "prompt": prompt,
            "enhance_prompt": True,
            # "seed": seed,
            # "steps": 30,
            "model": model,
            "frames": frames,
            "input_image": {
                "id": image_data.get("id"),
                "url": image_data.get("url"),
                "type": "media_input",
            },
            # "input_image_end": None,
            # "width": 1024,
            # "height": 1024,
            # "input_audio": None,
            # "input_video": None,
            "motion_id": motion_params.get("id"),
        }
    }

    token = get_token()
    res = requests.post(
        "https://fnf.higgsfield.ai/jobs/image2video",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    return res.json()
