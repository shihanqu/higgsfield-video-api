#!/usr/bin/env python3
"""
Launch Playwright, log in to Higgsfield, and keep the browser open while logging network traffic.

Use this script when you need to manually trigger actions (e.g., generate an image) and capture the
exact API requests Playwright sees. Press Enter in the terminal once you're finished to close the
session and save the latest storage state to auth.json.
"""

import sys
from pathlib import Path

from environs import Env
from playwright.sync_api import Playwright, sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
APP_ROOT = SCRIPTS_DIR.parent
PROJECT_ROOT = APP_ROOT.parent
REPO_ROOT = PROJECT_ROOT.parent

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
LOG_PATH = APP_ROOT / "playwright_network.log"


def require(value: str, name: str) -> str:
    if not value:
        print(f"Missing {name}. Set it in .env.credentials or pass via environment.", file=sys.stderr)
        sys.exit(1)
    return value


def run(playwright: Playwright, email: str, password: str) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    def log_request(request):
        if "fnf.higgsfield.ai" in request.url or "clerk.higgsfield.ai" in request.url:
            with LOG_PATH.open("a", encoding="utf-8") as log_file:
                log_file.write(
                    f"REQUEST {request.method} {request.url}\n"
                    f"Headers: {request.headers}\n"
                    f"Post data: {request.post_data or ''}\n"
                    "---------------------------------------\n"
                )

    def log_response(response):
        if "fnf.higgsfield.ai" in response.url or "clerk.higgsfield.ai" in response.url:
            try:
                body = response.text()
            except Exception:
                body = "<non-textual body>"
            with LOG_PATH.open("a", encoding="utf-8") as log_file:
                log_file.write(
                    f"RESPONSE {response.status} {response.url}\n"
                    f"Headers: {response.headers}\n"
                    f"Body: {body}\n"
                    "=======================================\n"
                )

    page.on("request", log_request)
    page.on("response", log_response)

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

        page.wait_for_url("https://higgsfield.ai/**", timeout=60000)
        page.wait_for_timeout(2000)

        print("Browser is ready. Perform any actions you need, then press Enter here to exit.")
        input()

        context.storage_state(path=str(OUTPUT_PATH))
        print(f"Saved Playwright storage state to {OUTPUT_PATH}")
        print(f"Network log written to {LOG_PATH}")
    finally:
        context.close()
        browser.close()


def main():
    email = require(LOGIN_EMAIL, "HIGGSFIELD_LOGIN_EMAIL")
    password = require(LOGIN_PASSWORD, "HIGGSFIELD_LOGIN_PASSWORD")

    # Clear old log
    LOG_PATH.write_text("", encoding="utf-8")

    with sync_playwright() as playwright:
        run(playwright, email=email, password=password)


if __name__ == "__main__":
    main()

