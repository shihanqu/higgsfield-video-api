#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path

from rebrowser_playwright.async_api import async_playwright

from src.repository.core import init_db
from src.repository.models.account import HiggsfieldAccount

USERNAME = "emilerdstrom"

SECRET_KEYS_FILE = f"secret_keys/{USERNAME}.json"


async def create_new_account():
    await init_db()
    auth_path = Path(SECRET_KEYS_FILE)
    output_path = Path("temp_auth.json")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # run headless for automation
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
        context = await browser.new_context(storage_state=auth_path)
        page = await context.new_page()
        await page.goto("https://higgsfield.ai/create/video")

        await page.context.storage_state(path=output_path)

        await browser.close()
        new_auth = json.loads(output_path.read_text())
        new_cookies = [
            c
            for c in new_auth.get("cookies", [])
            if "higgsfield.ai" in c.get("domain", "")
        ]

        new_account = HiggsfieldAccount(username=USERNAME, cookies_json=new_cookies)

        output_path.unlink()

        await new_account.save()


if __name__ == "__main__":
    asyncio.run(create_new_account())
    print("Account created successfully")
