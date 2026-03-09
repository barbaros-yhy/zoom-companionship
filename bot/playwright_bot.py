# bot/playwright_bot.py
import asyncio
import os
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
            'input[class*="name"],'
            'input:not(.hideme)'
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
                "--disable-web-security",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--window-size=1280,800",
            ],
            env={
                **dict(os.environ),  # inherit full environment (PULSE_SERVER etc.)
                "PULSE_SINK": "virtual_sink",
                "PULSE_SOURCE": "virtual_sink.monitor",
            },
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

        # Capture browser console logs for debugging
        self._page.on("console", lambda msg: print(f"[browser console] {msg.type}: {msg.text}"))

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

            // Override getUserMedia to provide fake audio stream
            // This makes Zoom think real audio device is available
            const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
            navigator.mediaDevices.getUserMedia = async function(constraints) {
                console.log('[getUserMedia override] constraints:', constraints);

                // For audio requests, create a fake audio stream
                if (constraints && constraints.audio) {
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const destination = audioContext.createMediaStreamDestination();
                    const oscillator = audioContext.createOscillator();
                    oscillator.connect(destination);
                    oscillator.start();
                    console.log('[getUserMedia override] returning fake audio stream');
                    return destination.stream;
                }

                // For video, try real getUserMedia (will use fake device from --use-fake-ui-for-media-stream)
                return originalGetUserMedia(constraints);
            };
        """)

        if "/j/" in meeting_url and "/wc/" not in meeting_url:
            meeting_url = meeting_url.replace("zoom.us/j/", "zoom.us/wc/join/")

        await self._page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # --- Step 1: Fill name using Playwright API (triggers proper validation) ---
        await self._page.screenshot(path="/tmp/zoom_debug.png")
        title = await self._page.title()
        print(f"[bot] Page title: {title}")

        # Try to find and fill name input using Playwright API
        name_input = await self._page.query_selector(self.SELECTORS["name_input"])
        if name_input:
            print("[bot] Name input found, filling with Playwright API...")
            await name_input.fill(self.display_name)
            await asyncio.sleep(0.5)
        else:
            print("[bot] No visible name input (may be cached)")

        # Click join button on name page
        join_btn = await self._page.query_selector(self.SELECTORS["join_button"])
        if join_btn:
            print("[bot] Join button found, clicking...")
            await self._page.evaluate("(el) => el.click()", join_btn)
            await asyncio.sleep(3)

        # --- Step 2: Preview page - click Join even if disabled ---
        await self._page.screenshot(path="/tmp/zoom_preview.png")
        print(f"[bot] After join URL: {self._page.url}")

        # Zoom's Join button may be disabled but still clickable
        preview_join = await self._page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('button'));
                const btn = btns.find(b => {
                    const t = b.textContent.trim().toLowerCase();
                    const a = (b.getAttribute('aria-label') || '').toLowerCase();
                    return t === 'join' || t === 'join meeting' || t === 'join now' ||
                           a === 'join' || a === 'join meeting';
                });
                if (btn) {
                    btn.click();
                    return btn.textContent.trim();
                }
                return null;
            }
        """)
        if preview_join:
            print(f"[bot] Clicked preview Join: '{preview_join}'")
            await asyncio.sleep(3)
        else:
            print("[bot] No preview Join button found")

        # --- Step 3: Wait for actual admission into the meeting ---
        # Indicator: Chat or Participants button only appear once inside the meeting.
        # Preview page and waiting room do NOT have these buttons.
        print("[bot] Waiting to be admitted to meeting...")
        for i in range(60):  # 60 x 5s = 5 minutes
            await asyncio.sleep(5)

            in_meeting = await self._page.query_selector(
                'button[aria-label="Chat"], '
                'button[aria-label="Participants"], '
                'button[aria-label="Share Screen"]'
            )
            if in_meeting:
                lbl = await in_meeting.get_attribute("aria-label")
                print(f"[bot] Admitted to meeting! (detected: {lbl})")
                break

            # Debug every iteration
            url = self._page.url
            buttons = await self._page.query_selector_all("button[aria-label]")
            labels = [await b.get_attribute("aria-label") for b in buttons[:15]]
            labels = [l for l in labels if l]
            print(f"[bot] Waiting... url={url.split('/')[-1]} buttons={labels}")

            # Screenshot every 30s
            if i % 6 == 0:
                await self._page.screenshot(path=f"/tmp/zoom_wait_{i}.png")
                print(f"[bot] Screenshot: /tmp/zoom_wait_{i}.png")
        else:
            print("[bot] WARNING: Timed out waiting for admission (5 min)")

        # --- Step 4: Take screenshot and log all buttons after admission ---
        await self._page.screenshot(path="/tmp/zoom_admitted.png")
        print(f"[bot] Admitted URL: {self._page.url}")
        print("[bot] Buttons after admission:")
        all_buttons = await self._page.query_selector_all("button")
        for i, b in enumerate(all_buttons[:25]):
            lbl = await b.get_attribute("aria-label") or ""
            txt = (await b.inner_text()).strip()[:60]
            print(f"[bot]   [{i}] aria='{lbl}' text='{txt}'")

        # --- Step 5: Join computer audio ---
        await asyncio.sleep(2)

        # Dismiss any open dialogs (OK button)
        ok_btn = await self._page.query_selector('button[aria-label="OK"]')
        if ok_btn:
            print("[bot] Dismissing dialog (OK button)...")
            await self._page.evaluate("(el) => el.click()", ok_btn)
            await asyncio.sleep(1)

        # Check if audio is already joined (Mute/Unmute present = already in audio)
        already_in_audio = await self._page.query_selector(
            'button[aria-label="Mute"], button[aria-label="Unmute"], '
            'button[aria-label="Mute my microphone"], button[aria-label="Unmute my microphone"]'
        )
        if already_in_audio:
            print("[bot] Audio already joined (Mute/Unmute button present)")
        else:
            # Find audio button
            audio_btn = await self._page.query_selector(
                'button[aria-label="audio"], button[aria-label="Audio"]'
            )
            if not audio_btn:
                print("[bot] No audio button found in toolbar")
            else:
                # --- DIAGNOSTIC: Log state BEFORE clicking ---
                print("[bot] Audio button found. State BEFORE click:")
                audio_state_before = await self._page.evaluate("""
                    () => {
                        const btn = document.querySelector('button[aria-label="audio"], button[aria-label="Audio"]');
                        if (!btn) return null;
                        return {
                            aria: btn.getAttribute('aria-label'),
                            text: btn.textContent.trim(),
                            class: btn.className,
                            disabled: btn.disabled
                        };
                    }
                """)
                print(f"[bot]   aria='{audio_state_before['aria']}' disabled={audio_state_before['disabled']}")

                # Cancel any stuck "Joining Meeting..." auto-join attempt
                print("[bot] Checking for stuck auto-join...")
                await asyncio.sleep(2)

                joining_stuck = await self._page.evaluate("""
                    () => {
                        const smallTexts = Array.from(document.querySelectorAll('div, span, p')).filter(e =>
                            e.textContent.length < 100 && e.textContent.includes('Joining Meeting')
                        );
                        return smallTexts.length > 0;
                    }
                """)

                audio_clicked = False
                if joining_stuck:
                    print("[bot] 'Joining Meeting...' detected - canceling by clicking audio button")
                    await self._page.evaluate("(el) => el.click()", audio_btn)
                    audio_clicked = True
                    await asyncio.sleep(2)

                    # Check if canceled
                    still_joining = await self._page.evaluate("""
                        () => {
                            const smallTexts = Array.from(document.querySelectorAll('div, span, p')).filter(e =>
                                e.textContent.length < 100 && e.textContent.includes('Joining Meeting')
                            );
                            return smallTexts.length > 0;
                        }
                    """)
                    if still_joining:
                        print("[bot] Auto-join still stuck after click, trying Close buttons...")
                        closed = await self._page.evaluate("""
                            () => {
                                const closeButtons = Array.from(document.querySelectorAll('button')).filter(b =>
                                    b.getAttribute('aria-label') === 'Close' ||
                                    b.textContent.trim().toLowerCase() === 'close' ||
                                    b.textContent.trim().toLowerCase() === 'cancel'
                                );
                                closeButtons.forEach(b => b.click());
                                return closeButtons.length;
                            }
                        """)
                        print(f"[bot] Clicked {closed} Close buttons")
                        await asyncio.sleep(1)
                    else:
                        print("[bot] Auto-join canceled!")
                else:
                    print("[bot] No auto-join detected")

                # Check if audio joined automatically or via cancel click
                mute_after_wait = await self._page.query_selector(
                    'button[aria-label="Mute"], button[aria-label="Unmute"]'
                )
                if mute_after_wait:
                    print("[bot] Audio already joined!")
                else:
                    # Click audio button to open menu (if not already clicked above)
                    if not audio_clicked:
                        print("[bot] Clicking audio button to open join menu...")
                        await self._page.evaluate("(el) => el.click()", audio_btn)
                        await asyncio.sleep(2)
                    else:
                        print("[bot] Audio button already clicked, checking for menu...")
                        await asyncio.sleep(1)

                    # --- DIAGNOSTIC: Log state AFTER clicking ---
                    print("[bot] State AFTER audio button click:")
                    audio_state_after = await self._page.evaluate("""
                        () => {
                            const btn = document.querySelector('button[aria-label="audio"], button[aria-label="Audio"]');
                            if (!btn) return null;
                            return {
                                aria: btn.getAttribute('aria-label'),
                                text: btn.textContent.trim(),
                                class: btn.className
                            };
                        }
                    """)
                    if audio_state_after:
                        print(f"[bot]   aria='{audio_state_after['aria']}'")
                    else:
                        print("[bot]   Audio button disappeared (may have changed aria-label)")

                    await self._page.screenshot(path="/tmp/zoom_audio_menu.png")

                    # Look for dropdown/menu/dialog elements that appeared
                    menu_elements = await self._page.evaluate("""
                        () => {
                            const menus = document.querySelectorAll('[role="menu"], [role="dialog"], .dropdown-menu, [class*="menu"]');
                            return Array.from(menus).slice(0, 5).map(m => ({
                                tag: m.tagName,
                                role: m.getAttribute('role'),
                                class: m.className.substring(0, 60),
                                visible: m.offsetParent !== null,
                                text: m.textContent.trim().substring(0, 100)
                            }));
                        }
                    """)
                    if menu_elements and len(menu_elements) > 0:
                        print(f"[bot] Found {len(menu_elements)} menu/dialog elements:")
                        for i, m in enumerate(menu_elements):
                            print(f"[bot]   [{i}] {m['tag']} role={m['role']} visible={m['visible']} text='{m['text'][:60]}'")

                    # Try to find and click "Join Audio" option
                    joined = await self._page.evaluate("""
                        () => {
                            const all = Array.from(document.querySelectorAll('button, li, div, span, a'));
                            const el = all.find(e => {
                                const t = e.textContent.trim().toLowerCase();
                                const a = (e.getAttribute('aria-label') || '').toLowerCase();
                                return (t.includes('computer audio') || t.includes('join audio') ||
                                        t === 'join' || a.includes('computer audio')) &&
                                       e.offsetParent !== null;  // must be visible
                            });
                            if (el) {
                                el.click();
                                return el.tagName + ': "' + el.textContent.trim().substring(0, 60) + '"';
                            }
                            return null;
                        }
                    """)
                    if joined:
                        print(f"[bot] Clicked audio join option: {joined}")
                        await asyncio.sleep(2)
                    else:
                        print("[bot] No 'Join Audio' UI element found")
                        print("[bot] Trying keyboard shortcut Alt+A (join/mute audio)...")
                        await self._page.keyboard.press("Alt+a")
                        await asyncio.sleep(2)
                        print("[bot] Trying keyboard shortcut Ctrl+Alt+A...")
                        await self._page.keyboard.press("Control+Alt+a")
                        await asyncio.sleep(2)

        # --- FINAL CHECK: Did audio actually join? ---
        await asyncio.sleep(2)
        final_audio_state = await self._page.query_selector(
            'button[aria-label="Mute"], button[aria-label="Unmute"], '
            'button[aria-label="Mute my microphone"], button[aria-label="Unmute my microphone"], '
            'button[aria-label="mute my microphone"], button[aria-label="unmute my microphone"]'
        )
        if final_audio_state:
            lbl = await final_audio_state.get_attribute("aria-label")
            print(f"[bot] ✓ Audio joined successfully! Button now: '{lbl}'")

            # Check PulseAudio streams to verify browser is outputting audio
            import subprocess
            try:
                print("[bot] Checking PulseAudio sink-inputs (browser audio streams)...")
                result = subprocess.run(
                    ["pactl", "list", "sink-inputs"],
                    capture_output=True, text=True, timeout=5
                )
                if "Chromium" in result.stdout or "chromium" in result.stdout.lower():
                    print("[bot] ✓ Browser audio stream found in PulseAudio!")
                    # Show which sink it's connected to
                    lines = result.stdout.split('\n')
                    for i, line in enumerate(lines):
                        if 'Sink:' in line or 'application.name' in line:
                            print(f"[bot]   {line.strip()}")
                else:
                    print("[bot] ✗ No Chromium audio stream in PulseAudio")
                    print("[bot] Browser may be outputting to wrong sink or audio blocked")
                    # Show all sink-inputs for debugging
                    result_short = subprocess.run(
                        ["pactl", "list", "sink-inputs", "short"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result_short.stdout.strip():
                        print(f"[bot] Active streams: {result_short.stdout}")
                    else:
                        print("[bot] No active audio streams at all")
            except Exception as e:
                print(f"[bot] Could not check PulseAudio: {e}")
        else:
            # Still showing lowercase "audio" = NOT joined
            still_not_joined = await self._page.query_selector('button[aria-label="audio"]')
            if still_not_joined:
                print("[bot] ✗ Audio join FAILED - button still shows 'audio' (not Mute/Unmute)")
                print("[bot] Checking if browser is outputting audio to PulseAudio...")

                # Check for browser audio streams in PulseAudio
                import subprocess
                try:
                    result = subprocess.run(
                        ["pactl", "list", "sink-inputs", "short"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.stdout.strip():
                        print(f"[bot] Active audio streams: {result.stdout.strip()}")
                    else:
                        print("[bot] No active audio streams in PulseAudio (browser not playing audio)")
                except Exception as e:
                    print(f"[bot] Could not check PulseAudio streams: {e}")
            else:
                print("[bot] ? Audio button state unclear")

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
