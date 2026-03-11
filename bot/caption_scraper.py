# bot/caption_scraper.py
"""
Zoom Live Transcript DOM Scraper
Alternative to audio capture + Whisper pipeline.
"""
import asyncio
from typing import Callable, Awaitable
from playwright.async_api import Page


class CaptionScraper:
    """Scrapes Zoom's native Live Transcript feature via DOM MutationObserver."""

    def __init__(self, page: Page, on_caption: Callable[[dict], Awaitable[None]]):
        """
        Args:
            page: Playwright page object (Zoom meeting)
            on_caption: Async callback when new caption detected
                        Receives: {"speaker": str, "text": str, "timestamp": str}
        """
        self.page = page
        self.on_caption = on_caption
        self._active = False

    async def enable_captions(self) -> bool:
        """
        Enable Zoom Live Transcript panel and inject scraper.

        Returns:
            True if captions enabled successfully, False otherwise
        """
        print("[caption_scraper] Step 1: Opening Live Transcript panel...")

        # STEP 1: Try to click "Show Captions" / "Closed Caption" button
        caption_button = None
        for selector in [
            'button[aria-label="Closed Caption"]',
            'button[aria-label="Show Captions"]',
            'button[aria-label="closed caption"]',
            'button[aria-label*="Caption" i]',
            'button[aria-label*="Subtitle" i]'
        ]:
            try:
                caption_button = await self.page.query_selector(selector)
                if caption_button:
                    is_visible = await caption_button.is_visible()
                    if is_visible:
                        label = await caption_button.get_attribute("aria-label")
                        print(f"[caption_scraper] Found caption button: '{label}'")
                        await caption_button.click()
                        await asyncio.sleep(2)
                        break
            except Exception as e:
                continue

        if not caption_button:
            print("[caption_scraper] No direct caption button found, trying 'More' menu...")

            # Try "More" (three dots) menu
            more_button = await self.page.query_selector(
                'button[aria-label="More"], '
                'button[aria-label="More options"]'
            )
            if more_button:
                await more_button.click()
                await asyncio.sleep(1)

                # Look for "Closed Caption" or "Captions" in menu
                menu_result = await self.page.evaluate("""
                    () => {
                        const items = Array.from(document.querySelectorAll(
                            'li, button, [role="menuitem"]'
                        ));
                        const captionItem = items.find(el => {
                            const text = el.textContent.toLowerCase();
                            return text.includes('caption') ||
                                   text.includes('subtitle') ||
                                   text.includes('transcript');
                        });
                        if (captionItem) {
                            captionItem.click();
                            return {success: true, text: captionItem.textContent.trim()};
                        }
                        return {success: false};
                    }
                """)

                if menu_result.get("success"):
                    print(f"[caption_scraper] Clicked menu item: '{menu_result['text']}'")
                    await asyncio.sleep(2)
                else:
                    print("[caption_scraper] Could not find caption option in More menu")
                    return False
            else:
                print("[caption_scraper] 'More' button not found")
                return False

        await self.page.screenshot(path="/data/zoom_captions_menu.png")

        # STEP 2: Check if "Request Captions" button appears (host hasn't enabled)
        print("[caption_scraper] Step 2: Checking if host permission needed...")

        request_button = await self.page.query_selector(
            'button:has-text("Request Captions"), '
            'button:has-text("Request"), '
            'button:has-text("Request Closed Caption")'
        )

        if request_button:
            print("[caption_scraper] ⚠️  Host hasn't enabled captions, requesting...")
            await request_button.click()
            await asyncio.sleep(2)

            # Wait for host approval (max 60 seconds)
            print("[caption_scraper] Waiting for host to approve caption request...")
            for i in range(12):  # 12 * 5s = 60 seconds
                await asyncio.sleep(5)

                # Check if transcript panel appeared
                transcript_panel = await self.page.query_selector(
                    '[class*="transcript"], '
                    '[class*="caption-panel"], '
                    '[data-testid*="transcript"]'
                )

                if transcript_panel:
                    print("[caption_scraper] ✓ Host approved! Transcript panel appeared")
                    break

                print(f"[caption_scraper] Still waiting... ({(i+1)*5}s)")
            else:
                print("[caption_scraper] ✗ Timeout: Host did not approve caption request")
                return False

        # STEP 3: Look for "View Full Transcript" / "Show Transcript" option
        print("[caption_scraper] Step 3: Opening full transcript panel...")

        full_transcript_result = await self.page.evaluate("""
            () => {
                const patterns = [
                    'view full transcript',
                    'full transcript',
                    'show transcript',
                    'transcript'
                ];

                const elements = Array.from(document.querySelectorAll(
                    'button, a, [role="button"], [role="menuitem"]'
                ));

                for (const pattern of patterns) {
                    const el = elements.find(e =>
                        e.textContent.toLowerCase().includes(pattern) &&
                        e.offsetParent !== null  // visible
                    );
                    if (el) {
                        el.click();
                        return {success: true, text: el.textContent.trim(), pattern};
                    }
                }

                return {success: false, foundButtons: elements
                    .filter(e => e.offsetParent !== null && e.textContent.trim().length > 0)
                    .map(e => e.textContent.trim().substring(0, 50))
                    .slice(0, 20)
                };
            }
        """)

        if not full_transcript_result.get("success"):
            print("[caption_scraper] Could not find 'View Full Transcript' button")
            print(f"[caption_scraper] Available buttons: {full_transcript_result.get('foundButtons', [])}")

            # Fallback: Captions might already be showing in-meeting (not panel)
            print("[caption_scraper] Checking if inline captions are visible...")
            inline_captions = await self.page.query_selector(
                '[class*="caption"], [class*="subtitle"], [data-testid*="caption"]'
            )
            if inline_captions:
                print("[caption_scraper] ✓ Inline captions detected, will scrape those")
            else:
                print("[caption_scraper] ✗ No captions visible at all")
                return False
        else:
            print(f"[caption_scraper] ✓ Clicked: '{full_transcript_result['text']}'")
            await asyncio.sleep(2)

        await self.page.screenshot(path="/data/zoom_transcript_panel.png")

        # STEP 4: Inject MutationObserver to scrape captions
        print("[caption_scraper] Step 4: Injecting MutationObserver scraper...")

        await self.page.expose_binding("sendCaptionToPython",
                                       lambda source, data: self._handle_caption(data))

        scraper_injected = await self.page.evaluate("""
            () => {
                // Prevent duplicate observers
                if (window.__captionObserverInstalled) {
                    console.log('[scraper] Observer already installed');
                    return {success: true, reason: 'already_installed'};
                }

                console.log('[scraper] Installing MutationObserver...');

                // Possible selectors for caption containers (Zoom changes these often)
                const containerSelectors = [
                    '[class*="transcript"]',
                    '[class*="caption-content"]',
                    '[class*="closed-caption"]',
                    '[data-testid*="transcript"]',
                    '[class*="subtitle"]'
                ];

                let targetContainer = null;
                for (const selector of containerSelectors) {
                    targetContainer = document.querySelector(selector);
                    if (targetContainer) {
                        console.log(`[scraper] Found container: ${selector}`);
                        break;
                    }
                }

                if (!targetContainer) {
                    console.error('[scraper] No transcript container found!');
                    return {success: false, reason: 'no_container'};
                }

                // Parse caption item (speaker + text)
                const parseCaption = (element) => {
                    // Zoom caption structure (typical):
                    // <div class="caption-item">
                    //   <span class="speaker-name">John Doe</span>
                    //   <span class="caption-text">Hello everyone</span>
                    // </div>

                    // Try multiple strategies
                    let speaker = 'Unknown';
                    let text = '';

                    // Strategy 1: Look for speaker-specific elements
                    const speakerEl = element.querySelector(
                        '[class*="speaker"], [class*="name"], [class*="author"]'
                    );
                    if (speakerEl) {
                        speaker = speakerEl.textContent.trim();
                    }

                    // Strategy 2: Look for text content
                    const textEl = element.querySelector(
                        '[class*="text"], [class*="content"], [class*="caption"]'
                    );
                    if (textEl) {
                        text = textEl.textContent.trim();
                    } else {
                        // Fallback: Get all text except speaker name
                        text = element.textContent.trim();
                        if (speaker !== 'Unknown') {
                            text = text.replace(speaker, '').trim();
                        }
                    }

                    // Strategy 3: If no speaker found, check if text starts with "Name: "
                    if (speaker === 'Unknown' && text.includes(':')) {
                        const parts = text.split(':', 2);
                        if (parts.length === 2 && parts[0].length < 50) {
                            speaker = parts[0].trim();
                            text = parts[1].trim();
                        }
                    }

                    return {speaker, text};
                };

                // Track processed captions to avoid duplicates
                const processedCaptions = new Set();

                const observer = new MutationObserver((mutations) => {
                    for (const mutation of mutations) {
                        for (const node of mutation.addedNodes) {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                // Check if this is a caption item
                                const isCaption =
                                    node.classList && (
                                        Array.from(node.classList).some(c =>
                                            c.includes('caption') ||
                                            c.includes('transcript') ||
                                            c.includes('subtitle')
                                        )
                                    );

                                if (isCaption) {
                                    const caption = parseCaption(node);

                                    // Only send if text is non-empty and not a duplicate
                                    if (caption.text && caption.text.length > 0) {
                                        const fingerprint = `${caption.speaker}:${caption.text}`;
                                        if (!processedCaptions.has(fingerprint)) {
                                            processedCaptions.add(fingerprint);

                                            // Clean up old entries (keep last 100)
                                            if (processedCaptions.size > 100) {
                                                const first = processedCaptions.values().next().value;
                                                processedCaptions.delete(first);
                                            }

                                            console.log(`[scraper] Caption: ${caption.speaker}: ${caption.text}`);

                                            // Send to Python
                                            window.sendCaptionToPython({
                                                speaker: caption.speaker,
                                                text: caption.text,
                                                timestamp: new Date().toISOString()
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    }
                });

                observer.observe(targetContainer, {
                    childList: true,
                    subtree: true
                });

                window.__captionObserverInstalled = true;
                console.log('[scraper] ✓ MutationObserver installed successfully');

                return {success: true, reason: 'installed'};
            }
        """)

        if not scraper_injected.get("success"):
            print(f"[caption_scraper] ✗ Failed to inject scraper: {scraper_injected.get('reason')}")
            return False

        print("[caption_scraper] ✓ Caption scraper installed successfully!")
        self._active = True
        return True

    async def _handle_caption(self, data: dict):
        """Internal callback when JS sends a caption to Python."""
        if not self._active:
            return

        # Call user's callback
        await self.on_caption(data)

    def is_active(self) -> bool:
        """Check if scraper is actively monitoring captions."""
        return self._active

    async def disable(self):
        """Stop scraping captions."""
        if self._active:
            # Remove observer
            await self.page.evaluate("""
                () => {
                    window.__captionObserverInstalled = false;
                    // Note: Can't actually stop MutationObserver without reference
                    // But we won't process events anymore
                }
            """)
            self._active = False
            print("[caption_scraper] Caption scraping disabled")
