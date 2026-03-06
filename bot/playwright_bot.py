# bot/playwright_bot.py
import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class ZoomBot:
    """Joins Zoom meetings via headless Chromium and scrapes active speaker."""

    # CSS selectors for Zoom web client — update if Zoom changes their UI
    SELECTORS = {
        "name_input": 'input[placeholder="Your Name"], input[aria-label="Please enter your name"]',
        "join_button": 'button[data-testid="joinBtn"], button.join-btn, #joinBtn, button[class*="join"]',
        "active_speaker": '[class*="active-speaker"] .participant-name, .active-speaker-name, [data-testid="active-speaker-name"]',
    }

    def __init__(self, display_name: str = "Companion"):
        self.display_name = display_name
        self.is_joined: bool = False
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None

    async def join(self, meeting_url: str):
        """Join a Zoom meeting via the web client."""
        async with async_playwright() as pw:
            self._playwright = pw
            self._browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    "--disable-web-security",
                ],
            )
            self._context = await self._browser.new_context(
                permissions=["microphone", "camera"],
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()

            # Convert zoom.us/j/ links to web client format if needed
            if "/j/" in meeting_url and "/wc/" not in meeting_url:
                meeting_url = meeting_url.replace("zoom.us/j/", "zoom.us/wc/join/")

            await self._page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)

            # Fill in display name if prompted
            name_input = await self._page.query_selector(self.SELECTORS["name_input"])
            if name_input:
                await name_input.fill(self.display_name)

            # Click join button if present
            join_btn = await self._page.query_selector(self.SELECTORS["join_button"])
            if join_btn:
                await join_btn.click()

            await asyncio.sleep(3)
            self.is_joined = True

    async def get_active_speaker(self) -> str | None:
        """Scrape the currently active speaker's display name from Zoom UI."""
        if not self._page:
            return None
        el = await self._page.query_selector(self.SELECTORS["active_speaker"])
        if el:
            return await el.inner_text()
        return None

    async def send_chat_message(self, message: str):
        """Send a message in the meeting chat."""
        if not self._page:
            return
        await self._page.keyboard.press("Alt+H")
        await asyncio.sleep(0.5)
        chat_input = await self._page.query_selector(
            '[placeholder*="message"], .chat-input textarea, [data-testid="chat-input"]'
        )
        if chat_input:
            await chat_input.fill(message)
            await self._page.keyboard.press("Enter")

    async def leave(self):
        """Leave the meeting and clean up browser resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.is_joined = False
        self._page = None
        self._browser = None
        self._context = None
