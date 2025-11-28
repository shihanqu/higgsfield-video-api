#!/usr/bin/env python3
"""
Deprecated wrapper kept for backwards compatibility.

NOTE: This script has been superseded by manage_accounts.py in the parent directory.
      Use `python manage_accounts.py add --cookies-file <file> --username <name>` instead.
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
APP_ROOT = SCRIPTS_DIR.parent
PROJECT_ROOT = APP_ROOT.parent
REPO_ROOT = PROJECT_ROOT.parent

for path in (APP_ROOT, PROJECT_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.repository.core import init_db  # noqa: E402
from src.repository.models.account import HiggsfieldAccount  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deprecated: use 'python manage_accounts.py add' instead."
    )
    parser.add_argument(
        "--cookies-file",
        required=True,
        help="Path to a JSON file with cookies (same format as Playwright storage).",
    )
    parser.add_argument("--username", required=True, help="Account username label.")
    return parser.parse_args()


async def persist_account(username: str, cookies_file: Path):
    import json

    await init_db()
    data = json.loads(Path(cookies_file).read_text(encoding="utf-8"))
    cookies = data.get("cookies", [])
    if not cookies:
        raise ValueError("No cookies found in the provided file.")

    account = await HiggsfieldAccount.get_or_none(username=username)
    if account:
        account.cookies_json = cookies
        await account.save()
        action = "Updated"
    else:
        await HiggsfieldAccount.create(username=username, cookies_json=cookies)
        action = "Created"
    print(f"{action} Higgsfield account '{username}'.")


def main():
    args = parse_args()
    try:
        import asyncio

        asyncio.run(persist_account(args.username, Path(args.cookies_file)))
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to save account: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

