#!/usr/bin/env python3
"""
Unified Higgsfield account management script.

Commands:
  login     Full flow: Playwright login -> save auth.json -> add to database
  capture   Only capture auth.json via Playwright (don't add to DB)
  add       Add/update account from existing auth.json to database
  list      List all stored accounts

Examples:
  python manage_accounts.py login
  python manage_accounts.py login --force
  python manage_accounts.py list
  python manage_accounts.py list --verbose
  python manage_accounts.py add --username "user@example.com"
  python manage_accounts.py capture --force
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

import requests
from environs import Env
from playwright.sync_api import Playwright, sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = APP_ROOT.parent
REPO_ROOT = PROJECT_ROOT.parent

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.repository.core import init_db
from src.repository.models.account import HiggsfieldAccount
from src.services import higgsfield_sync

# ─────────────────────────────────────────────────────────────────────────────
# Environment Setup
# ─────────────────────────────────────────────────────────────────────────────

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
AUTH_JSON_PATH = APP_ROOT / "auth.json"
TOKEN_CHECK_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/141.0"


# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────


def require_env(value: Optional[str], name: str) -> str:
    """Ensure an environment variable is set."""
    if not value:
        print(f"Missing {name}. Set it in .env.credentials or pass via environment.", file=sys.stderr)
        sys.exit(1)
    return value


def auth_state_has_valid_token(storage_path: Path) -> bool:
    """Check if existing auth.json has a valid session."""
    if not storage_path.exists():
        return False

    try:
        jar = higgsfield_sync.load_cookiejar(storage_path)
    except Exception as exc:
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
    except Exception as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        print(f"Existing auth.json failed token validation: {exc}")
        return False


def load_cookies_from_file(path: Path) -> List[dict]:
    """Load and filter Higgsfield cookies from a Playwright storage state file."""
    if not path.exists():
        raise FileNotFoundError(f"Cookies file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    cookies = data.get("cookies")
    if not isinstance(cookies, list):
        raise ValueError("Cookies file must contain a 'cookies' array.")

    filtered = [c for c in cookies if "higgsfield.ai" in c.get("domain", "")]
    if not filtered:
        raise ValueError(
            "No Higgsfield cookies found. Make sure you exported storage after logging in."
        )
    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# Playwright Capture
# ─────────────────────────────────────────────────────────────────────────────


def run_playwright_login(playwright: Playwright, email: str, password: str) -> None:
    """Run Playwright browser login and save storage state."""
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

        context.storage_state(path=str(AUTH_JSON_PATH))
        print(f"Saved Playwright storage state to {AUTH_JSON_PATH}")
    finally:
        context.close()
        browser.close()


def capture_auth(force: bool = False) -> bool:
    """Capture auth via Playwright. Returns True if capture was performed."""
    if not force and auth_state_has_valid_token(AUTH_JSON_PATH):
        print(
            f"{AUTH_JSON_PATH} already contains a valid Clerk session. "
            "Use --force to capture a fresh login."
        )
        return False

    email = require_env(LOGIN_EMAIL, "HIGGSFIELD_LOGIN_EMAIL")
    password = require_env(LOGIN_PASSWORD, "HIGGSFIELD_LOGIN_PASSWORD")

    with sync_playwright() as playwright:
        run_playwright_login(playwright, email=email, password=password)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Database Operations
# ─────────────────────────────────────────────────────────────────────────────


async def add_account_to_db(username: str, cookies_file: Path, inactive: bool) -> None:
    """Add or update an account in the database from a cookies file."""
    await init_db()
    cookies = load_cookies_from_file(cookies_file)

    account = await HiggsfieldAccount.get_or_none(username=username)
    if account:
        account.cookies_json = cookies
        account.is_active = not inactive
        await account.save()
        action = "Updated"
    else:
        await HiggsfieldAccount.create(
            username=username,
            cookies_json=cookies,
            is_active=not inactive,
        )
        action = "Created"

    state = "inactive" if inactive else "active"
    print(f"{action} Higgsfield account '{username}' ({state}).")


async def list_accounts(verbose: bool = False) -> None:
    """List all stored accounts."""
    await init_db()
    accounts = await HiggsfieldAccount.all()

    if not accounts:
        print("No Higgsfield accounts found.")
        return

    print(f"Found {len(accounts)} Higgsfield account(s):\n")
    for account in accounts:
        status = "active" if account.is_active else "inactive"
        print(f"  {account.username} ({status}) - {len(account.cookies_json)} cookies")

        if verbose:
            for cookie in account.cookies_json:
                name = cookie.get("name", "?")
                domain = cookie.get("domain", "?")
                print(f"      {name:25} {domain}")
            print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI Commands
# ─────────────────────────────────────────────────────────────────────────────


def cmd_login(args: argparse.Namespace) -> None:
    """Full login flow: capture auth + add to database."""
    captured = capture_auth(force=args.force)

    if captured or AUTH_JSON_PATH.exists():
        username = args.username or LOGIN_EMAIL
        if not username:
            print(
                "Username missing. Provide --username or set HIGGSFIELD_LOGIN_EMAIL.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            asyncio.run(add_account_to_db(username, AUTH_JSON_PATH, args.inactive))
        except Exception as exc:
            print(f"Failed to add account: {exc}", file=sys.stderr)
            sys.exit(1)


def cmd_capture(args: argparse.Namespace) -> None:
    """Capture auth only (don't add to database)."""
    capture_auth(force=args.force)


def cmd_add(args: argparse.Namespace) -> None:
    """Add account from existing auth.json to database."""
    username = args.username or LOGIN_EMAIL
    if not username:
        print(
            "Username missing. Provide --username or set HIGGSFIELD_LOGIN_EMAIL.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        asyncio.run(add_account_to_db(username, args.cookies_file, args.inactive))
    except Exception as exc:
        print(f"Failed to add account: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    """List all stored accounts."""
    asyncio.run(list_accounts(verbose=args.verbose))


# ─────────────────────────────────────────────────────────────────────────────
# Argument Parser
# ─────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage Higgsfield accounts (login, add, list).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s login                    # Full login flow
  %(prog)s login --force            # Force re-login even if session valid
  %(prog)s capture                  # Only capture auth.json
  %(prog)s add                      # Add existing auth.json to DB
  %(prog)s list                     # List all accounts
  %(prog)s list --verbose           # List with cookie details
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ─── login ───────────────────────────────────────────────────────────────
    login_parser = subparsers.add_parser(
        "login",
        help="Full flow: Playwright login -> auth.json -> database",
    )
    login_parser.add_argument(
        "--force",
        action="store_true",
        help="Force a new Playwright login even if auth.json is valid.",
    )
    login_parser.add_argument(
        "--username",
        default=None,
        help="Account username (defaults to HIGGSFIELD_LOGIN_EMAIL).",
    )
    login_parser.add_argument(
        "--inactive",
        action="store_true",
        help="Mark the account as inactive after importing.",
    )
    login_parser.set_defaults(func=cmd_login)

    # ─── capture ─────────────────────────────────────────────────────────────
    capture_parser = subparsers.add_parser(
        "capture",
        help="Only capture auth.json via Playwright (don't add to DB)",
    )
    capture_parser.add_argument(
        "--force",
        action="store_true",
        help="Force a new Playwright login even if auth.json is valid.",
    )
    capture_parser.set_defaults(func=cmd_capture)

    # ─── add ─────────────────────────────────────────────────────────────────
    add_parser = subparsers.add_parser(
        "add",
        help="Add/update account from existing auth.json to database",
    )
    add_parser.add_argument(
        "--username",
        default=None,
        help="Account username (defaults to HIGGSFIELD_LOGIN_EMAIL).",
    )
    add_parser.add_argument(
        "--cookies-file",
        type=Path,
        default=AUTH_JSON_PATH,
        help=f"Path to cookies JSON file (default: {AUTH_JSON_PATH}).",
    )
    add_parser.add_argument(
        "--inactive",
        action="store_true",
        help="Mark the account as inactive after importing.",
    )
    add_parser.set_defaults(func=cmd_add)

    # ─── list ────────────────────────────────────────────────────────────────
    list_parser = subparsers.add_parser(
        "list",
        help="List all stored Higgsfield accounts",
    )
    list_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show cookie details for each account.",
    )
    list_parser.set_defaults(func=cmd_list)

    return parser.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

