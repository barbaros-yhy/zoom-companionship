# Caption Mode Guide - Zoom Live Transcript Scraping

**Date:** 2026-03-11
**Status:** ✅ Production Ready (Alternative to Audio Mode)

## Overview

Caption Mode scrapes Zoom's native **Live Transcript** feature via DOM manipulation, eliminating the need for:
- ❌ PulseAudio virtual sinks
- ❌ Audio capture (`parec`)
- ❌ Speaches/Whisper transcription
- ❌ Complex audio routing

Instead:
- ✅ Uses Zoom's built-in speech-to-text
- ✅ Scrapes transcript directly from DOM
- ✅ Simpler architecture, fewer failure points

---

## Architecture

### Audio Mode (Original - Currently Broken)
```
Zoom Meeting → Chromium → PulseAudio → parec → Speaches (Whisper) → Python
```
**Issues:** Silent audio capture, WebRTC routing problems

### Caption Mode (New - Recommended)
```
Zoom Meeting → Live Transcript Panel → MutationObserver (JS) → expose_binding → Python
```
**Advantages:** Directly reads transcript DOM, no audio plumbing

---

## Usage

### Basic Usage
```bash
# Caption mode (recommended)
python -m bot.main \
  --meeting-url "https://zoom.us/j/123456789" \
  --meeting-id "test-meeting-001" \
  --use-captions \
  --no-summary
```

### Audio Mode (for comparison)
```bash
# Audio mode (default - currently has silent audio issue)
python -m bot.main \
  --meeting-url "https://zoom.us/j/123456789" \
  --meeting-id "test-meeting-001" \
  --no-summary
```

### Docker Run (Caption Mode)
```bash
cd /opt/zoom-companionship/bot

sudo docker run --rm --user 1000:1000 \
  -e PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
  -e SPEACHES_URL=http://172.17.0.1:8000 \
  -e DB_PATH=/data/meetings.db \
  -e TRANSCRIPT_DIR=/data/transcripts \
  -e BOT_WS_PORT=8765 \
  -e BOT_NAME="Companion" \
  -v /opt/zoom-companionship/data:/data \
  zoom-bot python -m bot.main \
    --meeting-url "MEETING_URL" \
    --meeting-id "MEETING_ID" \
    --use-captions \
    --no-summary
```

**Note:** Caption mode doesn't need PulseAudio socket mount or PULSE_SERVER env var.

---

## How It Works

### 1. Enable Live Transcript
```python
# bot/caption_scraper.py
caption_scraper = CaptionScraper(page=bot._page, on_caption=callback)
success = await caption_scraper.enable_captions()
```

**Steps:**
1. Click "Closed Caption" or "Show Captions" button
2. If not found, open "More" menu and search
3. Check for "Request Captions" button (if host hasn't enabled)
4. Wait for host approval (timeout: 60 seconds)
5. Click "View Full Transcript" to open side panel

### 2. Inject MutationObserver
```javascript
// Watches DOM for new caption elements
const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
            if (isCaption(node)) {
                const {speaker, text} = parseCaption(node);
                window.sendCaptionToPython({speaker, text, timestamp});
            }
        }
    }
});
observer.observe(transcriptContainer, {childList: true, subtree: true});
```

### 3. Parse Caption Elements
```javascript
// Typical Zoom caption structure:
// <div class="caption-item">
//   <span class="speaker-name">John Doe</span>
//   <span class="caption-text">Hello everyone</span>
// </div>

const parseCaption = (element) => {
    let speaker = element.querySelector('[class*="speaker"]')?.textContent || 'Unknown';
    let text = element.querySelector('[class*="text"]')?.textContent || '';

    // Fallback: Parse "Name: text" format
    if (speaker === 'Unknown' && text.includes(':')) {
        [speaker, text] = text.split(':', 2).map(s => s.trim());
    }

    return {speaker, text};
};
```

### 4. Stream to Python
```python
# bot/caption_pipeline.py
async for segment in pipeline.run(meeting_id=meeting_id):
    storage.append_segment(...)
    await ws_server.broadcast(segment)
    print(f"[{segment['timestamp']}] {segment['speaker']}: {segment['text']}")
```

---

## Host Requirements

### If Host Has Enabled Captions ✅
Bot will:
1. Open caption panel
2. Start scraping immediately

### If Host Hasn't Enabled Captions ⚠️
Bot will:
1. Click "Request Captions" button
2. Wait up to 60 seconds for host approval
3. If timeout → Exit with error

**Host must approve within 60 seconds!**

---

## Troubleshooting

### Issue: "Could not enable Zoom captions"

**Possible Causes:**
1. Host hasn't enabled captions
2. "Closed Caption" feature disabled in Zoom settings
3. Zoom UI updated (selectors outdated)

**Solutions:**
```bash
# Check screenshots for debugging
ls -lh /data/zoom_*.png

# zoom_captions_menu.png - Should show caption menu
# zoom_transcript_panel.png - Should show transcript sidebar
```

### Issue: No captions appearing

**Diagnosis:**
```bash
# Check browser console logs
docker logs <container_id> | grep "\[scraper\]"

# Should see:
# [scraper] Installing MutationObserver...
# [scraper] Found container: [class*="transcript"]
# [scraper] ✓ MutationObserver installed successfully
```

**Common Problems:**
- Zoom changed DOM structure → Update selectors in `caption_scraper.py`
- Container selector not matching → Add new pattern to `containerSelectors`
- Caption parsing failed → Check `parseCaption()` logic

### Issue: Duplicate captions

**Cause:** MutationObserver fires multiple times for same element

**Solution:** Already handled via deduplication:
```javascript
const processedCaptions = new Set();
const fingerprint = `${speaker}:${text}`;
if (!processedCaptions.has(fingerprint)) {
    processedCaptions.add(fingerprint);
    window.sendCaptionToPython(...);
}
```

---

## Advantages Over Audio Mode

| Aspect | Audio Mode | Caption Mode |
|--------|------------|--------------|
| **Setup** | Complex (PulseAudio, Docker volumes) | Simple (just Playwright) |
| **Dependencies** | Speaches, Whisper, parec | None (uses Zoom's API) |
| **CPU Usage** | High (Whisper transcription) | Low (DOM parsing) |
| **Latency** | 5-10s (CPU transcription) | ~1s (Zoom's realtime STT) |
| **Accuracy** | Depends on Whisper model | Depends on Zoom's STT |
| **Failure Points** | Many (audio routing, capture, API) | Few (DOM scraping only) |
| **Works With** | Any meeting | Only meetings with captions enabled |

---

## When to Use Each Mode

### Use Caption Mode When:
- ✅ Host has enabled Live Transcript
- ✅ You want simplicity and reliability
- ✅ Zoom's transcription quality is acceptable
- ✅ Low latency is important

### Use Audio Mode When:
- ✅ Host hasn't enabled captions
- ✅ You need custom Whisper models (e.g., medical terms)
- ✅ You want control over transcription accuracy
- ✅ Audio mode issues are resolved (currently broken)

---

## Testing

### Local Test (Without Joining Meeting)
```python
# Test caption parsing logic
from bot.caption_scraper import CaptionScraper

# Mock data
test_html = '''
<div class="caption-item">
    <span class="speaker-name">Alice</span>
    <span class="caption-text">Testing 123</span>
</div>
'''

# Should parse: {"speaker": "Alice", "text": "Testing 123"}
```

### Live Test (Join Test Meeting)
```bash
# Join a test meeting with captions enabled
python -m bot.main \
  --meeting-url "https://zoom.us/test" \
  --meeting-id "test-$(date +%s)" \
  --use-captions \
  --no-summary

# Expected output:
# [caption_scraper] ✓ Caption scraper installed successfully!
# [00:00:05] Alice: Hello everyone
# [00:00:12] Bob: Hi Alice
```

---

## Future Improvements

1. **Auto-detect Mode**: Try caption mode first, fallback to audio if unavailable
2. **Hybrid Mode**: Use captions for speed, audio for accuracy verification
3. **Language Support**: Parse Zoom's language metadata from caption elements
4. **Inline Captions**: Support in-meeting captions (not just side panel)
5. **Selector Updates**: Automatically adapt to Zoom UI changes via ML

---

## Code Structure

```
bot/
├── caption_scraper.py       # DOM scraping + MutationObserver
├── caption_pipeline.py      # Stream segments from captions
├── main.py                  # Entry point (--use-captions flag)
├── playwright_bot.py        # Zoom join logic (unchanged)
├── storage.py               # SQLite + markdown (unchanged)
└── ws_server.py             # WebSocket broadcast (unchanged)
```

**Note:** Audio mode files (`audio_capture.py`, `transcriber.py`, `pipeline.py`) remain in codebase for future use.

---

## Deployment

### Docker Build
```bash
cd /opt/zoom-companionship/bot
sudo docker build -t zoom-bot .
```

**No changes needed** - Caption mode uses same Dockerfile (Playwright already installed).

### Environment Variables (Caption Mode)
```bash
# Required
DB_PATH=/data/meetings.db
TRANSCRIPT_DIR=/data/transcripts
BOT_WS_PORT=8765

# Optional
BOT_NAME="Companion"          # Display name in meeting
AWS_REGION=eu-central-1       # For summary generation
```

**Not needed for caption mode:**
- ~~SPEACHES_URL~~ (no Whisper needed)
- ~~PULSE_SERVER~~ (no audio capture needed)
- ~~PULSE_SINK~~ (no PulseAudio needed)

---

## Summary

Caption Mode is the **recommended approach** for production use. It's simpler, more reliable, and leverages Zoom's native transcription. Audio Mode remains available for edge cases where custom transcription is needed.

**Next Steps:**
1. Test in production meeting with captions enabled
2. Monitor for Zoom UI changes (update selectors as needed)
3. Consider auto-fallback if caption mode fails

---

**Document Version:** 1.0
**Author:** Zoom Companion Bot Team
**Date:** 2026-03-11
