import asyncio

from rebrowser_playwright.async_api import async_playwright

OUTPUT_FILE = "secret_keys/first_account.json"


async def simple_higgsfield_auth():
    """Simple Higgsfield authentication without Inspector"""

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=BlockThirdPartyCookies",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
                "--use-mock-keychain",
            ],
        )
        page = await browser.new_page()

        print("🌐 Opening Higgsfield authentication page...")

        # Try to navigate to Higgsfield
        try:
            await page.goto("https://higgsfield.ai/auth", timeout=30000)
            print("✅ Loaded Higgsfield auth page")
        except Exception:
            print("⚠️ Auth page failed, trying main page...")
            await page.goto("https://higgsfield.ai", timeout=30000)
            print("✅ Loaded Higgsfield main page")

        # Show current URL
        current_url = page.url
        print(f"📍 Current URL: {current_url}")

        # Show page title
        title = await page.title()
        print(f"📄 Page title: {title}")

        print("\n🔍 Please complete authentication in the browser:")
        print("   1. If you see a login page, click 'Continue with Google'")
        print("   2. Complete Google authentication")
        print("   3. Wait for redirect to main Higgsfield page")
        print("   4. Come back here and press Enter")

        # Wait for user to complete auth
        input("\n✅ Press Enter when authentication is complete...")

        # Capture the authentication state
        print("💾 Saving authentication state...")
        await page.context.storage_state(path=OUTPUT_FILE)

        # Get final URL after auth
        final_url = page.url
        print(f"📍 Final URL: {final_url}")

        # Count cookies
        cookies = await page.context.cookies()
        print(f"🍪 Saved {len(cookies)} cookies")

        print(f"✅ Authentication saved to {OUTPUT_FILE}!")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(simple_higgsfield_auth())
