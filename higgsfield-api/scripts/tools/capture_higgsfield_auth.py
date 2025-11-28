#!/usr/bin/env python3
"""
Automate a Higgsfield login via Playwright and export the storage state.

The script now reuses the existing auth.json if it can still mint a token,
only launching Playwright when the stored session is invalid. Pass --force to
refresh the storage unconditionally.

Credentials are read from the same `.env` files used elsewhere:
- `higgsfield-api/.env.credentials`
- `higgsfield-api/.env`
- repo root `.env`

NOTE: This script has been superseded by manage_accounts.py in the parent directory.
      Use `python manage_accounts.py capture` instead.
"""

import argparse
import sys
from pathlib import Path

import requests
from environs import Env
from playwright.sync_api import Playwright, sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
APP_ROOT = SCRIPTS_DIR.parent
PROJECT_ROOT = APP_ROOT.parent
REPO_ROOT = PROJECT_ROOT.parent

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.services import higgsfield_sync  # noqa: E402

env = Env()
_ENV_LOADED = False
for candidate in (
    APP_ROOT / ".env.credentials",
    APP_ROOT / ".env",
    REPO_ROOT / ".env",
):
    if candidate.exists():
        env.read_env(candidate)
        _ENV_LOADED = True
        break

LOGIN_EMAIL = env.str("HIGGSFIELD_LOGIN_EMAIL", default=None) if _ENV_LOADED else None
LOGIN_PASSWORD = env.str("HIGGSFIELD_LOGIN_PASSWORD", default=None) if _ENV_LOADED else None
OUTPUT_PATH = APP_ROOT / "auth.json"
TOKEN_CHECK_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/141.0"


def require(value: str, name: str) -> str:
    if not value:
        print(f"Missing {name}. Set it in .env.credentials or pass via environment.", file=sys.stderr)
        sys.exit(1)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Higgsfield auth storage with Playwright, reusing existing tokens when possible."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force a new Playwright login even if auth.json still yields a valid token.",
    )
    return parser.parse_args()


def auth_state_has_valid_token(storage_path: Path) -> bool:
    if not storage_path.exists():
        return False

    try:
        jar = higgsfield_sync.load_cookiejar(storage_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Existing auth.json is unreadable: {exc}")
        return False

    try:
        with requests.Session() as session:
            session.cookies.update(jar)
            session.headers.update({"User-Agent": TOKEN_CHECK_USER_AGENT})

            sid = higgsfield_sync.try_session_id_from_clerk_active_context(jar)
            if not sid:
                sid = higgsfield_sync.try_session_id_from___session_jwt(jar)
            if not sid:
                sid = higgsfield_sync.get_session_id_via_api(session)
            if not sid:
                return False

            higgsfield_sync.mint_session_token(session, sid)
            return True
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):  # pragma: no cover - pass through interrupts
            raise
        print(f"Existing auth.json failed token validation: {exc}")
        return False


def run(playwright: Playwright, email: str, password: str) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    try:
        page.goto("https://higgsfield.ai/", wait_until="domcontentloaded")
        page.get_by_role("link", name="Login").click()
        page.get_by_role("link", name="Continue with Email").click()

        email_box = page.get_by_role("textbox", name="Email")
        email_box.fill(email)
        page.get_by_role("button", name="Continue").click()

        password_box = page.get_by_role("textbox", name="Password")
        password_box.fill(password)
        page.get_by_role("button", name="Log in").click()

        try:
            page.wait_for_url("https://higgsfield.ai/**", timeout=60000)
        except Exception:
            page.wait_for_timeout(3000)

        # Give Clerk time to sync cookies/session storage
        page.wait_for_timeout(2000)

        context.storage_state(path=str(OUTPUT_PATH))
        print(f"Saved Playwright storage state to {OUTPUT_PATH}")
    finally:
        context.close()
        browser.close()


def main():
    args = parse_args()

    if not args.force and auth_state_has_valid_token(OUTPUT_PATH):
        print(
            f"{OUTPUT_PATH} already contains a valid Clerk session. "
            "Use --force to capture a fresh login."
        )
        return

    email = require(LOGIN_EMAIL, "HIGGSFIELD_LOGIN_EMAIL")
    password = require(LOGIN_PASSWORD, "HIGGSFIELD_LOGIN_PASSWORD")

    with sync_playwright() as playwright:
        run(playwright, email=email, password=password)


if __name__ == "__main__":
    main()

