#!/usr/bin/env python3
"""
Print stored Higgsfield accounts and the cookies we have on file.

NOTE: This script has been superseded by manage_accounts.py in the parent directory.
      Use `python manage_accounts.py list` instead.
"""

import asyncio
import json
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


async def main():
    await init_db()
    accounts = await HiggsfieldAccount.all()
    print(f"Found {len(accounts)} Higgsfield account(s).")
    for account in accounts:
        print("-" * 80)
        print(f"Username: {account.username}")
        print(f"Active: {account.is_active}")
        print(f"Cookies stored: {len(account.cookies_json)} entries")
        for cookie in account.cookies_json:
            name = cookie.get("name")
            domain = cookie.get("domain")
            print(f"  {name:25} {domain}")


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)

