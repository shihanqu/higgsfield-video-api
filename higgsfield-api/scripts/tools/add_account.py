#!/usr/bin/env python3
"""
Store or refresh a Higgsfield account in the local database.

Provide a JSON file containing Higgsfield cookies (e.g. a Playwright storage state)
and this script will insert/update the corresponding HiggsfieldAccount record.

NOTE: This script has been superseded by manage_accounts.py in the parent directory.
      Use `python manage_accounts.py add` instead.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

from environs import Env

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
APP_ROOT = SCRIPTS_DIR.parent
REPO_ROOT = APP_ROOT.parent.parent

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.repository.core import init_db  # noqa: E402
from src.repository.models.account import HiggsfieldAccount  # noqa: E402


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

DEFAULT_USERNAME = env.str("HIGGSFIELD_LOGIN_EMAIL", default=None) if _ENV_LOADED else None
DEFAULT_COOKIES = APP_ROOT / "auth.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add or update a Higgsfield account using a cookies JSON file."
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help="Reference name for this account (defaults to HIGGSFIELD_LOGIN_EMAIL).",
    )
    parser.add_argument(
        "--cookies-file",
        default=DEFAULT_COOKIES,
        type=Path,
        help="Path to a JSON file with a `cookies` array (defaults to auth.json).",
    )
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Mark the account as inactive after importing (defaults to active).",
    )
    return parser.parse_args()


def load_cookies(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Cookies file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    cookies = data.get("cookies")
    if not isinstance(cookies, list):
        raise ValueError("Cookies file must contain a 'cookies' array.")

    filtered = [
        c for c in cookies if "higgsfield.ai" in c.get("domain", "")
    ]
    if not filtered:
        raise ValueError(
            "No Higgsfield cookies found. Make sure you exported storage after logging in."
        )
    return filtered


async def async_main(username: str, cookies_file: Path, inactive: bool):
    await init_db()
    cookies = load_cookies(cookies_file)

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


def main():
    args = parse_args()
    if not args.username:
        print(
            "Username missing. Provide --username or set HIGGSFIELD_LOGIN_EMAIL in .env.credentials.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        asyncio.run(async_main(args.username, args.cookies_file, args.inactive))
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to add account: {exc}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

