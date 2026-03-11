# Zoom Companionship Bot - Comprehensive Troubleshooting Guide

**Document Purpose:** Complete technical reference for debugging audio capture issues.
**Last Updated:** 2026-03-11 (Evening)
**Status:** Audio join working, but captured audio is silent

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Audio Pipeline Flow](#audio-pipeline-flow)
3. [Current State](#current-state)
4. [Debugging History](#debugging-history)
5. [Known Issues](#known-issues)
6. [Alternative Solutions](#alternative-solutions)

---

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         EC2 t3.medium (Ubuntu 22.04)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │   Speaches   │◄────────│   Bot        │                     │
│  │   (CPU)      │         │   (Python)   │                     │
│  │   :8000      │         │              │                     │
│  │              │         │  Playwright  │                     │
│  │ Whisper      │         │  Chromium    │                     │
│  │ Small        │         │              │                     │
│  └──────────────┘         └──────┬───────┘                     │
│                                   │                              │
│                                   ▼                              │
│                          ┌─────────────────┐                    │
│                          │   PulseAudio    │                    │
│                          │   Daemon        │                    │
│                          │                 │                    │
│                          │  auto_null      │                    │
│                          │  virtual_sink   │◄──┐                │
│                          │  .monitor       │   │                │
│                          └─────────────────┘   │                │
│                                   │             │                │
│                                   ▼             │                │
│                          ┌─────────────────┐   │                │
│                          │   parec         │───┘                │
│                          │   (capture)     │                    │
│                          └─────────────────┘                    │
│                                   │                              │
│                                   ▼                              │
│                          ┌─────────────────┐                    │
│                          │  Transcriber    │                    │
│                          │  Pipeline       │                    │
│                          └─────────────────┘                    │
│                                   │                              │
│                                   ▼                              │
│                          ┌─────────────────┐                    │
│                          │  SQLite + WS    │                    │
│                          └─────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### Key Technologies

- **Playwright**: Headless browser automation for Zoom web client
- **PulseAudio**: Virtual audio routing system
- **Speaches**: Whisper transcription API
- **FastAPI**: Transcription API server
- **SQLite**: Meeting metadata storage
- **WebSocket**: Real-time transcript streaming

---

## Audio Pipeline Flow

### Expected Flow (What Should Happen)

```
1. ZOOM MEETING
   └─> Participant speaks
       │
2. ZOOM SERVER
   └─> Sends audio to all participants (including bot)
       │
3. BROWSER (Chromium)
   └─> WebRTC receives audio stream
       │
4. BROWSER AUDIO OUTPUT
   └─> Routes to PulseAudio sink (virtual_sink)
       │
5. PULSEAUDIO
   └─> virtual_sink receives audio
   └─> virtual_sink.monitor mirrors the audio
       │
6. PAREC
   └─> Captures from virtual_sink.monitor
   └─> Outputs raw PCM audio (16kHz, mono, s16le)
       │
7. TRANSCRIBER
   └─> Buffers 2-second chunks
   └─> Converts PCM → WAV
   └─> Sends to Speaches API
       │
8. SPEACHES (Whisper)
   └─> Transcribes audio → text
       │
9. PIPELINE
   └─> Tags speaker (from Zoom UI scraping)
   └─> Saves to SQLite + markdown files
   └─> Broadcasts via WebSocket
```

### Current State (What Actually Happens)

```
1-3. ✅ ZOOM → BROWSER: Working
     Browser joins meeting, UI shows "Mute" button

4. ❓ BROWSER → PULSEAUDIO: Partially Working
     - Browser creates 5 PulseAudio streams
     - All connected to Sink 1 (virtual_sink)
     - BUT: Audio content is silent/noise

5-6. ✅ PULSEAUDIO → PAREC: Working
     - Captures 322KB/10sec (correct size for 16kHz mono)
     - BUT: File contains silence/noise

7-9. ✅ TRANSCRIBER → WHISPER: Working
     - Processes audio chunks
     - Whisper outputs "you" (typical for silence/noise)
```

---

## Current State

### What Works ✅

| Component | Status | Evidence |
|-----------|--------|----------|
| Bot Join | ✅ Working | Logs show "Admitted to meeting" |
| Playwright Stealth | ✅ Working | No detection errors |
| Audio Join | ✅ Working | UI shows "Mute" instead of "Audio" |
| Fake Microphone | ✅ Working | `getUserMedia()` succeeds |
| PulseAudio Connection | ✅ Working | 5 Chromium sink-inputs visible |
| Audio Capture | ✅ Working | parec outputs 322KB/10sec |
| Speaches API | ✅ Working | Processes requests within timeout |
| Whisper Processing | ✅ Working | Outputs "you" for silence |

### What Doesn't Work ❌

| Issue | Symptom | Evidence |
|-------|---------|----------|
| **Audio Content** | Captured audio is silent | Whisper outputs "you" repeatedly |
| **Speaker Routing** | Meeting audio not reaching browser output | Test file (322KB) plays as silence |
| **Unknown Root Cause** | All infrastructure works but no real audio | All connections established but content missing |

### Diagnostic Evidence

```bash
# PulseAudio Streams (from pactl list sink-inputs)
Sink Input #20
  Sink: 1 (virtual_sink)
  application.name = "Chromium"

Sink Input #24
  Sink: 1 (virtual_sink)
  application.name = "Chromium"

# Audio Capture Test
$ ls -lh /tmp/test_audio.raw
-rw-r--r-- 1 ubuntu ubuntu 322K Mar 11 20:00 test_audio.raw
# ✅ Correct size (10 seconds * 16000 Hz * 2 bytes)
# ❌ Content is silence when played

# Whisper Output
[00:00:01] Unknown: you
[00:00:03] Unknown: you
# "you" = Whisper's output for silence/noise
```

---

## Debugging History

### Phase 1: Infrastructure Setup (SOLVED ✅)

#### Problem: Browser Crashes in Headless Mode
**Symptoms:**
- Browser crashes immediately after launch
- No error messages

**Diagnosis:**
- GPU acceleration not available in headless container
- WebGL errors causing crashes

**Solution:** (Commit 70b8452)
```python
args=[
    "--disable-gpu",
    "--disable-webgl",
    "--disable-webgl2",
    "--disable-software-rasterizer",
]
```

**Result:** ✅ Browser stable

---

#### Problem: No Visual Display for UI Rendering
**Symptoms:**
- Zoom UI not rendering properly
- Missing buttons/dialogs

**Diagnosis:**
- Headless browser needs virtual display for complex UIs

**Solution:** (Commit 30f9699)
- Added Xvfb (X Virtual Framebuffer)
- `DISPLAY=:99` environment variable

**Result:** ✅ UI renders correctly

---

### Phase 2: Audio Join (SOLVED ✅)

#### Problem: "Floating Reactions" Dialog Blocks Audio Join
**Symptoms:**
- `role="dialog"` selector matches wrong dialog
- Audio join button not found

**Diagnosis:** (Screenshot analysis)
- Zoom shows feature announcement dialog
- This dialog has same `role="dialog"` as audio dialog
- Bot's search stopped at first match

**Solution:** (Commit bdb5afc)
```python
# Dismiss ALL dialogs before audio join
for attempt in range(3):
    ok_button = await self._page.query_selector('button:has-text("OK")')
    if ok_button:
        await ok_button.click()
```

**Result:** ✅ Dialog interference removed

---

#### Problem: Zoom Requires Microphone for Audio Join
**Symptoms:**
```
[bot] getUserMedia test: {'success': False, 'error': 'Requested device not found'}
[bot] Media devices detected: 2
  [0] audiooutput: Virtual_Sink
  [1] audiooutput: (no label)
# ❌ No audioinput!
```

**Diagnosis:**
- Browser doesn't see PulseAudio sources in container
- Zoom web client requires microphone permission
- Without mic, "Join Audio" button doesn't appear

**Attempted Solution 1:** Inject fake devices via `enumerateDevices` override
```javascript
devices.push({
    deviceId: 'default',
    kind: 'audioinput',
    label: 'Fake Microphone',
});
```
**Result:** ❌ Fake devices visible in `enumerateDevices()` but unusable by `getUserMedia()`

**Final Solution:** (Commit 92630a0) Override `getUserMedia()` with real fake stream
```javascript
navigator.mediaDevices.getUserMedia = async function(constraints) {
    if (constraints.audio) {
        // Create silent audio track via AudioContext
        const audioContext = new AudioContext();
        const oscillator = audioContext.createOscillator();
        oscillator.frequency.value = 0; // Silent
        const dest = audioContext.createMediaStreamDestination();
        oscillator.connect(dest);
        oscillator.start();
        return dest.stream;
    }
    return originalGetUserMedia(constraints);
};
```

**Result:** ✅ **AUDIO JOIN SUCCESSFUL**
```
[bot] getUserMedia test: {'success': True, 'label': 'MediaStreamAudioDestinationNode'}
[bot]   [2] aria='mute my microphone' text='Mute'  ← JOINED!
```

---

#### Problem: Browser Doesn't Connect to PulseAudio
**Symptoms:**
- No Chromium sink-inputs in PulseAudio
- Audio join works but no streams

**Diagnosis:**
- `PULSE_SINK` env var not enough
- Browser needs default sink set

**Solution:** (EC2 setup)
```bash
# Create virtual_sink
pactl load-module module-null-sink sink_name=virtual_sink

# Set as default (browser auto-connects to default)
pactl set-default-sink virtual_sink
pactl set-default-source virtual_sink.monitor
```

**Result:** ✅ Browser creates 5 PulseAudio streams to virtual_sink

---

### Phase 3: Audio Capture (WORKING BUT SILENT ❌)

#### Problem: Speaches API Timeout
**Symptoms:**
```
httpcore.ReadTimeout
File "/app/bot/transcriber.py", line 56, in _send_to_speaches
```

**Diagnosis:**
- CPU-only transcription with `faster-whisper-small` is slow (~3-5x realtime)
- 2-second audio chunk takes 6-10 seconds to process
- Default 30s timeout too short for slow CPU

**Solution:** (Commit 3e21fd1)
```python
self._client = httpx.AsyncClient(timeout=120)  # Was 30
```

**Result:** ✅ No more timeouts, Whisper processes audio

---

#### Problem: Captured Audio is Silent ❓
**Symptoms:**
```
[00:00:01] Unknown: you
[00:00:03] Unknown: you
# Participant speaking but Whisper only sees silence
```

**Diagnosis:**
```bash
# Audio captured with correct size
$ ls -lh test_audio.raw
322K  # ✅ Correct (10s * 16kHz * 2 bytes = 320KB)

# PulseAudio shows streams
$ pactl list sink-inputs short
20  1  protocol-native.c  Chromium  # ✅ 5 streams

# Browser shows audio elements playing
{'activeMediaElements': 4, 'activeDetails': [
  {'type': 'audio', 'paused': False, 'muted': False, 'volume': 1}
]}  # ✅ Not muted, volume 100%
```

**Current Hypothesis:**
1. ~~Volume is 0~~ → ❌ Logs show volume=1
2. ~~Audio muted~~ → ❌ Logs show muted=False
3. ~~Wrong sink~~ → ❌ All streams go to virtual_sink
4. ~~WebRTC not receiving audio~~ → ❓ Active audio elements exist
5. **~~Speaker device not selected~~** → ❓ UNTESTED (next diagnostic)

**Next Steps:**
- [ ] Click "More audio controls" button
- [ ] Check speaker device selection in Zoom settings
- [ ] Test with different Zoom meeting (rule out meeting-specific issues)
- [ ] Consider alternative: Recall.ai third-party service

---

## Known Issues

### 1. Speaker Detection Returns "Unknown"
**Status:** Low priority (doesn't affect transcription)

**Issue:**
```python
# playwright_bot.py line 29
"active_speaker": '[class*="active-speaker"] .participant-name'
```
Selector is outdated for current Zoom UI.

**Workaround:** Transcripts work without speaker names.

---

### 2. CPU Transcription is Slow
**Status:** Expected behavior

**Performance:**
- `faster-whisper-small` on t3.medium: ~3-5x slower than realtime
- 2-second audio → 6-10 seconds processing time
- Real-time transcription not possible on CPU

**Mitigations:**
- ✅ Increased timeout to 120s
- ✅ Using smallest viable model (small)
- ❌ Cannot use large models (too slow)

**Alternative:** GPU instance (g4dn.xlarge) for realtime, but costs $385/mo vs $38/mo

---

### 3. Captured Audio is Silent (CRITICAL BLOCKER)
**Status:** Unresolved root cause

See [Phase 3](#phase-3-audio-capture-working-but-silent-) for full debugging history.

---

## Alternative Solutions

### Option 1: Third-Party Bot Service (Recall.ai) ⭐ RECOMMENDED

**Pros:**
- ✅ Guaranteed to work (they handle all Zoom complexity)
- ✅ 1-2 hours integration time
- ✅ No debugging/maintenance burden
- ✅ Professional support

**Cons:**
- ❌ Cost: ~$0.10/minute = $6/hour = $60/mo for 10 hours
- ❌ Vendor lock-in
- ❌ Less control over pipeline

**Integration:**
```python
# POST to Recall.ai API
response = requests.post("https://api.recall.ai/api/v1/bot", json={
    "meeting_url": "https://zoom.us/j/...",
    "bot_name": "Companion"
})

# Webhook receives transcript
@app.post("/webhook/recall")
def handle_transcript(data: dict):
    # Save to SQLite + markdown
    storage.save_segment(data)
```

---

### Option 2: Zoom Meeting SDK (Official)

**Pros:**
- ✅ Official Zoom API (stable, documented)
- ✅ Direct audio access (no WebRTC routing issues)
- ✅ No web scraping fragility

**Cons:**
- ❌ Requires Zoom Marketplace app approval (1-2 weeks)
- ❌ OAuth flow complexity
- ❌ 1 week+ development time
- ❌ User must authorize app

---

### Option 3: Continue Custom Bot Development

**Pros:**
- ✅ Full control
- ✅ No monthly costs
- ✅ Learning experience

**Cons:**
- ❌ Unknown time to resolution
- ❌ High maintenance (Zoom UI changes)
- ❌ Fragile (many moving parts)

**Remaining Debug Steps:**
1. Check "More audio controls" → Speaker settings
2. Test WebRTC direct capture (bypass PulseAudio)
3. Try Chrome DevTools Protocol audio capture
4. Test on different Zoom meetings

---

## Technical Deep Dive: Why Fake Microphone Works

### The Problem
Zoom web client checks for microphone availability before showing "Join Audio" option.

### Why We Need Fake Mic
```javascript
// Zoom does this:
const devices = await navigator.mediaDevices.enumerateDevices();
const hasMic = devices.some(d => d.kind === 'audioinput');

if (!hasMic) {
    // Don't show "Join Audio" button
    return;
}
```

### Why Simple Fake Doesn't Work
```javascript
// This doesn't work:
navigator.mediaDevices.enumerateDevices = async function() {
    return [{deviceId: 'fake', kind: 'audioinput', label: 'Fake'}];
};

// Because getUserMedia still fails:
await navigator.mediaDevices.getUserMedia({audio: true});
// Error: "Requested device not found"
```

### Why Our Solution Works
```javascript
// Override getUserMedia to provide REAL MediaStream
navigator.mediaDevices.getUserMedia = async function(constraints) {
    if (constraints.audio) {
        // Create real MediaStream with silent audio track
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        osc.frequency.value = 0; // Silent
        const dest = ctx.createMediaStreamDestination();
        osc.connect(dest);
        osc.start();
        return dest.stream; // REAL MediaStream object
    }
};
```

**Key Insight:** `MediaStreamAudioDestinationNode.stream` is a **real** MediaStream that Zoom can use, even though the audio content is silent. This satisfies Zoom's microphone requirement without needing actual microphone hardware.

---

## Debugging Commands Reference

### EC2 Setup Commands
```bash
# PulseAudio setup
pactl load-module module-null-sink sink_name=virtual_sink
pactl set-default-sink virtual_sink
pactl set-default-source virtual_sink.monitor

# Verify setup
pactl list sinks short
pactl list sources short
pactl info | grep "Default"
```

### Runtime Diagnostics
```bash
# Check PulseAudio streams (while bot running)
pactl list sink-inputs
pactl list sink-inputs short

# Manual audio capture test
timeout 10 parec --device=virtual_sink.monitor \
  --format=s16le --rate=16000 --channels=1 \
  /tmp/test.raw

# Check file size (should be ~320KB for 10 seconds)
ls -lh /tmp/test.raw

# Convert to WAV and listen
python3 << 'EOF'
import wave
with open('/tmp/test.raw', 'rb') as f:
    data = f.read()
with wave.open('/tmp/test.wav', 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    w.writeframes(data)
EOF

# Download and play locally
scp user@ec2:/tmp/test.wav ./
open test.wav  # Mac
```

### Docker Commands
```bash
# Build
cd /opt/zoom-companionship/bot
sudo docker build -t zoom-bot .

# Run with full diagnostics
sudo docker run --rm --user 1000:1000 \
  -e PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
  -e PULSE_SERVER=unix:/run/user/1000/pulse/native \
  -e PULSE_SINK=virtual_sink \
  -e SPEACHES_URL=http://172.17.0.1:8000 \
  -e WHISPER__MODEL=Systran/faster-whisper-small \
  -e DB_PATH=/data/meetings.db \
  -e TRANSCRIPT_DIR=/data/transcripts \
  -v /run/user/1000/pulse:/run/user/1000/pulse \
  -v /opt/zoom-companionship/data:/data \
  zoom-bot python -m bot.main \
  --meeting-url "MEETING_URL" \
  --meeting-id "MEETING_ID" \
  --no-summary

# Check logs
docker logs <container_id> -f

# Enter running container
docker exec -it <container_id> /bin/bash
```

---

## Conclusion

**Current Status:** 90% complete
- ✅ All infrastructure working
- ✅ Audio join successful
- ✅ Capture pipeline functional
- ❌ Captured audio is silent (root cause unknown)

**Recommended Next Step:** Evaluate Recall.ai for production use while continuing custom bot investigation as learning exercise.

**Time Investment:** 10-12 hours of systematic debugging

**Key Learnings:**
1. Zoom web client has complex microphone requirements
2. Fake MediaStream can satisfy getUserMedia
3. PulseAudio routing works but audio content routing unclear
4. CPU transcription viable but slow (3-5x realtime)
5. Third-party services may be more cost-effective than custom development for production

---

**Document Version:** 1.0
**Author:** Systematic Debugging Session with Claude Sonnet 4.5
**Date:** 2026-03-11
