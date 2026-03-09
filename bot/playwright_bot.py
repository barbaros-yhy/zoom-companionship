# bot/playwright_bot.py
import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import stealth_async


class ZoomBot:
    """Joins Zoom meetings via headless Chromium and scrapes active speaker."""

    SELECTORS = {
        "name_input": (
            'input[placeholder="Your Name"],'
            'input[placeholder="Please enter your name"],'
            'input[aria-label="Please enter your name"],'
            'input[aria-label="Your Name"],'
            'input.preview-name-input,'
            'input[class*="name"]'
        ),
        "join_button": (
            'button[data-testid="joinBtn"],'
            'button.join-btn,'
            '#joinBtn,'
            'button[class*="join"],'
            'button.preview-join-button,'
            'button[class*="preview"][class*="join"]'
        ),
        "active_speaker": '[class*="active-speaker"] .participant-name, .active-speaker-name, [data-testid="active-speaker-name"]',
    }

    ALLOWED_HOSTS = {"zoom.us", "us02web.zoom.us", "us04web.zoom.us", "us06web.zoom.us"}

    def __init__(self, display_name: str = "Companion"):
        self.display_name = display_name
        self.is_joined: bool = False
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None

    def _validate_url(self, url: str):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.hostname not in self.ALLOWED_HOSTS:
            raise ValueError(f"URL hostname '{parsed.hostname}' is not an allowed Zoom host.")

    async def join(self, meeting_url: str):
        """Join a Zoom meeting via the web client. Keeps browser open until leave() is called."""
        self._validate_url(meeting_url)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--disable-web-security",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--window-size=1280,800",
            ],
        )
        self._context = await self._browser.new_context(
            permissions=["microphone", "camera"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
        )
        self._page = await self._context.new_page()

        # Apply stealth patches (playwright-stealth handles 20+ detection vectors)
        await stealth_async(self._page)

        # Additional manual patches on top of stealth
        await self._page.add_init_script("""
            // Realistic screen dimensions
            Object.defineProperty(screen, 'width', { get: () => 1280 });
            Object.defineProperty(screen, 'height', { get: () => 800 });
            Object.defineProperty(screen, 'availWidth', { get: () => 1280 });
            Object.defineProperty(screen, 'availHeight', { get: () => 760 });
            Object.defineProperty(screen, 'colorDepth', { get: () => 24 });

            // Realistic hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

            // Connection type
            Object.defineProperty(navigator, 'connection', {
                get: () => ({ effectiveType: '4g', rtt: 50, downlink: 10 })
            });
        """)

        if "/j/" in meeting_url and "/wc/" not in meeting_url:
            meeting_url = meeting_url.replace("zoom.us/j/", "zoom.us/wc/join/")

        await self._page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Debug: log page state
        title = await self._page.title()
        url = self._page.url
        content = await self._page.content()
        print(f"[bot] Page title: {title}")
        print(f"[bot] Current URL: {url}")
        if "not supported" in content.lower() or "download" in content.lower():
            print("[bot] WARNING: Zoom showing 'Browser not supported' page!")
        if "Your Name" in content or "your name" in content.lower():
            print("[bot] SUCCESS: Name input page detected!")

        # Save screenshot for visual inspection
        await self._page.screenshot(path="/tmp/zoom_debug.png")
        print("[bot] Screenshot saved to /tmp/zoom_debug.png")

        # Try to find and fill name input
        name_input = await self._page.query_selector(self.SELECTORS["name_input"])
        if name_input:
            print("[bot] Name input found, filling...")
            await name_input.fill(self.display_name)
            await asyncio.sleep(0.5)
        else:
            print("[bot] WARNING: Name input NOT found, dumping input fields...")
            inputs = await self._page.query_selector_all("input")
            for i, inp in enumerate(inputs):
                ph = await inp.get_attribute("placeholder") or ""
                aria = await inp.get_attribute("aria-label") or ""
                cls = await inp.get_attribute("class") or ""
                print(f"[bot]   input[{i}]: placeholder='{ph}' aria='{aria}' class='{cls}'")

        # Try to find and click join button
        join_btn = await self._page.query_selector(self.SELECTORS["join_button"])
        if join_btn:
            print("[bot] Join button found, clicking via JS...")
            # Use JS click to bypass overlay interception
            await self._page.evaluate("(el) => el.click()", join_btn)
        else:
            print("[bot] WARNING: Join button NOT found, dumping buttons...")
            buttons = await self._page.query_selector_all("button")
            for i, btn in enumerate(buttons):
                txt = await btn.inner_text()
                cls = await btn.get_attribute("class") or ""
                print(f"[bot]   button[{i}]: text='{txt.strip()}' class='{cls[:60]}')")

        await asyncio.sleep(3)
        self.is_joined = True

    async def get_active_speaker(self) -> str | None:
        if not self._page:
            return None
        el = await self._page.query_selector(self.SELECTORS["active_speaker"])
        if el:
            return await el.inner_text()
        return None

    async def send_chat_message(self, message: str):
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
        """Leave the meeting and clean up all browser resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.is_joined = False
        self._page = None
        self._browser = None
        self._context = None
        self._playwright = None
