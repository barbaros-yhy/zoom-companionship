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
                # CRITICAL: Auto-accept media permission prompts
                "--use-fake-ui-for-media-stream",
                # CRITICAL: Use native fake audio device instead of JS override
                # This prevents WebRTC APM (echo cancellation) interference
                "--use-fake-device-for-media-stream",
                "--use-file-for-fake-audio-capture=/app/bot/silent.wav",
                "--disable-web-security",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--window-size=1280,800",
                # FIX: Autoplay policy - allow media playback from bot interactions
                "--autoplay-policy=no-user-gesture-required",
                # FIX: Prevent headless mode from throttling media playback
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                # FIX: Reduce memory usage and prevent browser crashes
                "--disable-gpu",                   # Disable GPU acceleration
                "--disable-dev-shm-usage",         # Use /tmp instead of /dev/shm (limited in Docker)
                "--disable-software-rasterizer",   # Disable software rendering fallback
                "--disable-webgl",                 # Disable WebGL (Zoom complains it's unsupported anyway)
                "--disable-webgl2",                # Disable WebGL2
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
        """)

        # CRITICAL FIX: Force all WebRTC audio/video to use virtual_sink
        # Zoom may route audio through Web Audio API nodes instead of DOM elements
        # This ensures all media output goes to PulseAudio virtual_sink
        await self._page.add_init_script("""
            // Wait for media elements and force sink to virtual_sink
            const forceAudioSink = async () => {
                const mediaElements = document.querySelectorAll('audio, video');
                console.log(`[forceAudioSink] Found ${mediaElements.length} media elements`);

                for (const el of mediaElements) {
                    if (typeof el.setSinkId === 'function') {
                        try {
                            // Empty string = default system output (virtual_sink in our case)
                            await el.setSinkId('');
                            console.log(`[forceAudioSink] ✓ Sink set for ${el.tagName}`);
                        } catch (error) {
                            console.error('[forceAudioSink] Failed:', error);
                        }
                    }
                }
            };

            // Run immediately
            forceAudioSink();

            // Re-run when DOM changes (Zoom adds media elements dynamically)
            const observer = new MutationObserver((mutations) => {
                // Check if any audio/video elements were added
                for (const mutation of mutations) {
                    if (mutation.addedNodes.length > 0) {
                        for (const node of mutation.addedNodes) {
                            if (node.tagName === 'AUDIO' || node.tagName === 'VIDEO') {
                                console.log('[forceAudioSink] New media element detected');
                                forceAudioSink();
                                break;
                            }
                        }
                    }
                }
            });
            observer.observe(document.body, {childList: true, subtree: true});
        """)

        if "/j/" in meeting_url and "/wc/" not in meeting_url:
            meeting_url = meeting_url.replace("zoom.us/j/", "zoom.us/wc/join/")

        await self._page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # DEBUG: List actual media devices
        devices = await self._page.evaluate("""
            async () => {
                const devices = await navigator.mediaDevices.enumerateDevices();
                return devices.map(d => ({
                    kind: d.kind,
                    label: d.label || '(no label)',
                    deviceId: d.deviceId.substring(0, 20)
                }));
            }
        """)
        print(f"[bot] Media devices detected: {len(devices)}")
        for i, d in enumerate(devices):
            print(f"  [{i}] {d['kind']}: {d['label']}")

        # DEBUG: Test getUserMedia to see if audio actually works
        audio_test = await self._page.evaluate("""
            async () => {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                    const tracks = stream.getAudioTracks();
                    const track = tracks[0];
                    const settings = track.getSettings();
                    track.stop();
                    return {
                        success: true,
                        label: track.label,
                        settings: settings
                    };
                } catch (e) {
                    return {success: false, error: e.message};
                }
            }
        """)
        print(f"[bot] getUserMedia test: {audio_test}")

        # FIX: Resume AudioContext to enable media playback
        audio_ctx_state = await self._page.evaluate("""
            async () => {
                try {
                    const ctx = new AudioContext();
                    const before = ctx.state;
                    if (ctx.state === 'suspended') {
                        await ctx.resume();
                    }
                    return {before: before, after: ctx.state, sampleRate: ctx.sampleRate};
                } catch (e) {
                    return {error: e.message};
                }
            }
        """)
        print(f"[bot] AudioContext: {audio_ctx_state}")

        # --- Step 1: Fill name using Playwright API (triggers proper validation) ---
        await self._page.screenshot(path="/data/zoom_debug.png")
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
        await self._page.screenshot(path="/data/zoom_preview.png")
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
                await self._page.screenshot(path=f"/data/zoom_wait_{i}.png")
                print(f"[bot] Screenshot: /data/zoom_wait_{i}.png")
        else:
            print("[bot] WARNING: Timed out waiting for admission (5 min)")

        # --- Step 4: Take screenshot and log all buttons after admission ---
        await self._page.screenshot(path="/data/zoom_admitted.png")
        print(f"[bot] Admitted URL: {self._page.url}")
        print("[bot] Buttons after admission:")
        all_buttons = await self._page.query_selector_all("button")
        for i, b in enumerate(all_buttons[:25]):
            lbl = await b.get_attribute("aria-label") or ""
            txt = (await b.inner_text()).strip()[:60]
            print(f"[bot]   [{i}] aria='{lbl}' text='{txt}'")

        # --- Step 5: Join computer audio ---
        print("[bot] Starting audio join sequence...")

        # STEP 0: Dismiss ALL blocking dialogs and warnings first
        print("[bot] Dismissing blocking dialogs and warnings...")

        # Dismiss "Cannot detect microphone" warning (if present)
        # Try multiple selectors for the close button
        for selector in [
            'button[aria-label*="Close"]',
            'button[aria-label*="close"]',
            'button:has-text("×")',
            'button:has-text("✕")',
            '[role="alert"] button',
            '[class*="alert"] button[class*="close"]'
        ]:
            try:
                warning_close = await self._page.query_selector(selector)
                if warning_close:
                    visible = await warning_close.is_visible()
                    if visible:
                        print(f"[bot] Dismissing warning/alert with selector: {selector}")
                        await warning_close.click()
                        await asyncio.sleep(1)
                        break
            except Exception as e:
                pass

        # Dismiss "Floating reactions" and any other feature announcement dialogs
        for attempt in range(3):  # Try up to 3 times (multiple dialogs might appear)
            try:
                # Look for OK/Got it/Dismiss buttons in dialogs
                ok_button = await self._page.query_selector(
                    'button:has-text("OK"), '
                    'button:has-text("Got it"), '
                    'button:has-text("Dismiss"), '
                    'div[role="dialog"] button[type="button"]'
                )
                if ok_button:
                    btn_text = await ok_button.inner_text()
                    print(f"[bot] Dismissing dialog (button: '{btn_text}')...")
                    await ok_button.click()
                    await asyncio.sleep(1)
                else:
                    break  # No more dialogs to dismiss
            except Exception as e:
                break

        await self._page.screenshot(path="/data/zoom_after_dismiss.png")
        print("[bot] Screenshot after dismissing dialogs: /data/zoom_after_dismiss.png")

        # DIAGNOSTIC 1: Wait for audio dialog to appear AFTER clicking Audio button
        print("[bot] Clicking Audio button to trigger audio join menu...")

        # Click the Audio button in toolbar to open menu
        audio_button = await self._page.query_selector('button[aria-label="audio"]')
        if audio_button:
            print("[bot] Found Audio button, clicking to open menu...")
            await audio_button.click()
            await asyncio.sleep(2)  # Wait for menu to open
            await self._page.screenshot(path="/data/zoom_audio_menu.png")
            print("[bot] Screenshot after clicking Audio: /data/zoom_audio_menu.png")
        else:
            print("[bot] ✗ Audio button not found!")

        # Now look for "Join with Computer Audio" option in menu/dialog
        print("[bot] Searching for 'Join with Computer Audio' option...")
        join_btn_found = False

        # Try to find the join button in multiple ways
        for pattern in [
            "button:has-text('Join with Computer Audio')",
            "button:has-text('Join Audio')",
            "button:has-text('Computer Audio')",
            "li:has-text('Join with Computer Audio')",
            "li:has-text('Join Audio')",
            "[role='menuitem']:has-text('Computer Audio')",
            "[role='menuitem']:has-text('Join')"
        ]:
            try:
                join_btn = await self._page.query_selector(pattern)
                if join_btn:
                    visible = await join_btn.is_visible()
                    text = (await join_btn.inner_text()).strip()
                    print(f"[bot] ✓ Found with pattern '{pattern}': visible={visible}, text='{text}'")
                    if visible:
                        await join_btn.click()
                        print(f"[bot] ✓ Clicked: '{text}'")
                        join_btn_found = True
                        break
            except Exception as e:
                pass

        # FALLBACK 1: Try JavaScript-based search for menu items
        if not join_btn_found:
            print("[bot] Trying JavaScript-based search...")
            js_result = await self._page.evaluate("""
                () => {
                    // Search for menu items, list items, or buttons with join audio text
                    const elements = Array.from(document.querySelectorAll('button, li, [role="menuitem"], [role="option"]'));
                    const patterns = [
                        'join with computer audio',
                        'computer audio',
                        'join audio'
                    ];

                    for (const pattern of patterns) {
                        const el = elements.find(e =>
                            e.textContent.trim().toLowerCase().includes(pattern) &&
                            e.offsetParent !== null
                        );
                        if (el) {
                            el.click();
                            return {success: true, text: el.textContent.trim(), pattern: pattern};
                        }
                    }

                    return {success: false, allVisible: elements
                        .filter(e => e.offsetParent !== null && e.textContent.trim().length > 0)
                        .map(e => ({
                            tag: e.tagName.toLowerCase(),
                            text: e.textContent.trim().substring(0, 50),
                            role: e.getAttribute('role') || ''
                        }))
                        .slice(0, 15)
                    };
                }
            """)

            if js_result.get('success'):
                print(f"[bot] ✓ JS found and clicked: '{js_result['text']}'")
                join_btn_found = True
            else:
                print(f"[bot] ✗ JS search failed. Visible menu elements:")
                for i, el in enumerate(js_result.get('allVisible', [])):
                    print(f"  [{i}] <{el['tag']}> role='{el['role']}' text='{el['text']}'")

        # FALLBACK 2: Try keyboard shortcut
        if not join_btn_found:
            print("[bot] Trying Alt+A keyboard shortcut as final fallback...")
            await self._page.keyboard.press("Alt+a")
            await asyncio.sleep(2)

        # --- DEBUG: Check speaker settings via "More audio controls" ---
        print("[bot] Checking speaker settings...")
        more_audio_btn = await self._page.query_selector('button[aria-label="More audio controls"]')
        if more_audio_btn:
            print("[bot] Clicking 'More audio controls'...")
            await more_audio_btn.click()
            await asyncio.sleep(2)
            await self._page.screenshot(path="/data/zoom_audio_settings.png")
            print("[bot] Screenshot: /data/zoom_audio_settings.png")

            # Try to click "Audio Settings" or "Speaker Settings"
            settings_items = await self._page.query_selector_all('li, button, [role="menuitem"]')
            print(f"[bot] Menu items: {len(settings_items)}")
            for i, item in enumerate(settings_items[:15]):
                text = await item.inner_text() if await item.is_visible() else ""
                text = text.strip()[:60]
                if text:
                    print(f"  [{i}] {text}")

        # --- FINAL CHECK: Did audio actually join? ---
        print("[bot] Waiting for audio state to update...")
        await asyncio.sleep(3)

        # DEBUG: Check if browser is actually receiving audio from Zoom
        audio_debug = await self._page.evaluate("""
            async () => {
                // Check if there are any active audio elements
                const audioElements = Array.from(document.querySelectorAll('audio, video'));
                const activeAudio = audioElements.filter(el => !el.paused && el.readyState >= 2);

                // Check AudioContext
                const contexts = [];
                if (window.AudioContext || window.webkitAudioContext) {
                    // Can't enumerate all contexts, but we can check if media is playing
                }

                return {
                    totalMediaElements: audioElements.length,
                    activeMediaElements: activeAudio.length,
                    activeDetails: activeAudio.map(el => ({
                        type: el.tagName.toLowerCase(),
                        paused: el.paused,
                        muted: el.muted,
                        volume: el.volume,
                        readyState: el.readyState,
                        src: el.src ? el.src.substring(0, 50) : 'no src'
                    }))
                };
            }
        """)
        print(f"[bot] Browser audio debug: {audio_debug}")

        # Take final screenshot
        await self._page.screenshot(path="/data/zoom_final_audio_state.png")
        print("[bot] Final screenshot: /data/zoom_final_audio_state.png")

        # Check if Mute/Unmute button appeared (indicates successful audio join)
        final_audio_state = await self._page.query_selector(
            'button[aria-label="Mute"], button[aria-label="Unmute"], '
            'button[aria-label="Mute my microphone"], button[aria-label="Unmute my microphone"], '
            'button[aria-label="mute my microphone"], button[aria-label="unmute my microphone"]'
        )

        import subprocess
        if final_audio_state:
            lbl = await final_audio_state.get_attribute("aria-label")
            print(f"[bot] ✓ Audio joined successfully! Button now: '{lbl}'")

            # Check PulseAudio streams to verify browser is outputting audio
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
            print("[bot] ✗ Audio join FAILED - Mute/Unmute button not found")

            # Debug: Show current audio button state
            audio_buttons = await self._page.query_selector_all('button[aria-label*="audio" i], button[aria-label*="Audio"]')
            print(f"[bot] Audio-related buttons found: {len(audio_buttons)}")
            for i, btn in enumerate(audio_buttons[:5]):
                aria = await btn.get_attribute("aria-label") or ""
                text = (await btn.inner_text()).strip()[:40]
                visible = await btn.is_visible()
                print(f"  [{i}] visible={visible} aria='{aria}' text='{text}'")

            # Check PulseAudio anyway
            try:
                print("[bot] Checking PulseAudio streams (maybe audio joined but UI didn't update)...")
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
