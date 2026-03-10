# Zoom Companion Bot - Complete Architecture & Current Status

**Last Updated:** 2026-03-10
**Status:** Audio join works, transcription captures silence

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        EC2 Instance (t3.medium)                   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Docker Container: zoom-bot                   │   │
│  │                                                            │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  Playwright (headless Chromium)                  │    │   │
│  │  │  - playwright-stealth (20+ detection bypasses)   │    │   │
│  │  │  - JS patches (screen, navigator, connection)    │    │   │
│  │  │  - Chromium args: --use-fake-ui-for-media-stream │    │   │
│  │  │  - env: PULSE_SINK=virtual_sink                  │    │   │
│  │  │                                                    │    │   │
│  │  │  ┌──────────────────────────────────────────┐    │    │   │
│  │  │  │   Zoom Web Client (app.zoom.us)          │    │    │   │
│  │  │  │   - WebRTC audio/video                   │    │    │   │
│  │  │  │   - Active speaker detection              │    │    │   │
│  │  │  └──────────────────────────────────────────┘    │    │   │
│  │  │         │ audio output                            │    │   │
│  │  └─────────┼─────────────────────────────────────────┘    │   │
│  │            │                                               │   │
│  │            ↓                                               │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │  PulseAudio (via socket mount)                      │  │   │
│  │  │  /run/user/1000/pulse/native                        │  │   │
│  │  │                                                      │  │   │
│  │  │  Sink: virtual_sink (s16le 2ch 44100Hz)           │  │   │
│  │  │  Source: virtual_sink.monitor                      │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  │            │ monitor                                       │   │
│  │            ↓                                               │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │  parec (audio capture)                              │  │   │
│  │  │  --device=virtual_sink.monitor                      │  │   │
│  │  │  --format=s16le --rate=16000 --channels=1           │  │   │
│  │  │  Output: 2-second PCM chunks                        │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  │            │ raw audio chunks                              │   │
│  │            ↓                                               │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │  Transcriber                                         │  │   │
│  │  │  Sends WAV chunks to Speaches                       │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                 │ HTTP request                                  │
│                 ↓                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Docker Container: speaches                              │  │
│  │  Image: ghcr.io/speaches-ai/speaches:0.9.0-rc.3-cpu     │  │
│  │  Model: Systran/faster-whisper-small                     │  │
│  │  Port: 8000                                               │  │
│  │  POST /v1/audio/transcriptions                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                 │ transcript text                               │
│                 ↓                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  TranscriptPipeline                                       │  │
│  │  - Tags speaker from ZoomBot.get_active_speaker()        │  │
│  │  - Emits segments with timestamp                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│            │                │                                   │
│            ↓                ↓                                   │
│  ┌──────────────┐  ┌───────────────────────────────────────┐  │
│  │  Storage     │  │  TranscriptWSServer                    │  │
│  │  SQLite +    │  │  Port: 8765                            │  │
│  │  Markdown    │  │  Broadcasts to dashboard               │  │
│  └──────────────┘  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Detailed Component Flow

### 2.1 Join Meeting Flow

```
1. main.py starts bot
   ↓
2. ZoomBot.join(meeting_url)
   ├─ Launch Chromium with stealth patches
   ├─ Navigate to meeting URL
   ├─ Fill name input with Playwright API (.fill())
   ├─ Click join button
   ├─ Handle preview page (click Join if present)
   ├─ Wait for admission (detect Chat/Participants button)
   ├─ Dismiss OK dialog
   └─ Handle audio join:
      ├─ Check for "Joining Meeting..." stuck state
      ├─ Cancel auto-join if stuck (click audio button + Close buttons)
      ├─ Try keyboard shortcuts (Alt+A, Ctrl+Alt+A)
      └─ Verify: aria-label changes from "audio" to "mute my microphone"
```

### 2.2 Audio Capture Flow

```
Browser (Chromium)
   ↓ outputs audio via PulseAudio client
PulseAudio Server
   ├─ Sink: virtual_sink (ID: 1)
   │  └─ Receives browser audio output
   │
   └─ Source: virtual_sink.monitor
      └─ Mirrors virtual_sink for capture
         ↓
   parec process
      └─ Reads from virtual_sink.monitor
         └─ Outputs: 2-second PCM chunks (s16le, 16kHz, mono)
            ↓
   Transcriber.transcribe_chunk()
      └─ Converts to WAV, POSTs to Speaches
         ↓
   Speaches (Whisper)
      └─ Returns transcript text
         ↓
   TranscriptPipeline
      └─ Tags speaker, emits segment
```

## 3. Environment Configuration

### Docker Run Command (Current Working)
```bash
sudo docker run --rm --user 1000:1000 \
  -e PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
  -e PULSE_SERVER=unix:/run/user/1000/pulse/native \
  -e PULSE_SINK=virtual_sink \
  -e SPEACHES_URL=http://172.17.0.1:8000 \
  -e WHISPER__MODEL=Systran/faster-whisper-small \
  -e DB_PATH=/tmp/meetings.db \
  -e TRANSCRIPT_DIR=/tmp/transcripts \
  -v /run/user/1000/pulse:/run/user/1000/pulse \
  zoom-bot python -m bot.main \
    --meeting-url "MEETING_URL" \
    --meeting-id "MEETING_ID" \
    --no-summary
```

### Key Environment Variables
- `PULSE_SERVER`: Socket path to PulseAudio daemon
- `PULSE_SINK`: Target sink for browser audio output (virtual_sink)
- `SPEACHES_URL`: Whisper API endpoint
- `PLAYWRIGHT_BROWSERS_PATH`: Non-root Playwright install location

### Volume Mounts
- `/run/user/1000/pulse:/run/user/1000/pulse` → PulseAudio socket access

## 4. Current Status: What Works ✅

### 4.1 Bot Join Flow
- ✅ **Name input filling** (Playwright `.fill()` API)
- ✅ **Preview page detection** (finds "Join" button)
- ✅ **Waiting room** (detects Chat/Participants button, not just Mute)
- ✅ **Admission detection** (distinguishes preview vs actual meeting)

### 4.2 Stealth & Detection Bypass
- ✅ **playwright-stealth** (20+ patches active)
- ✅ **Manual JS patches** (screen, navigator, connection)
- ✅ **Browser console logging** (captures all logs for debugging)

### 4.3 Audio Join (Inconsistent)
**Working state (getUserMedia override):**
```
[bot]   [3] aria='mute my microphone' text='Mute'  ← SUCCESS
[bot] ✓ Browser audio stream found in PulseAudio!
[bot]   Sink: 1  ← Correct sink (virtual_sink)
```

**Current state (after revert):**
```
[bot]   [3] aria='audio' text='Audio'  ← FAILED
[bot] ✗ Audio join FAILED
```

### 4.4 PulseAudio Setup
- ✅ **virtual_sink created** (`pactl list sinks short` shows sink 1)
- ✅ **virtual_sink.monitor available** (`pactl list sources short`)
- ✅ **Browser connects to PulseAudio** (sink-inputs show Chromium streams)

## 5. Current Problem: Audio Transcription Failure ❌

### 5.1 Symptoms
```
[00:00:02] Unknown: you
[00:00:25] Unknown: you
[00:00:48] Unknown: you
```

Whisper outputs "you" repeatedly → hallucination on silence/noise

### 5.2 Evidence Gathered

**When audio join works:**
```bash
# PulseAudio shows browser streams
pactl list sink-inputs short
74  1  124  protocol-native.c  float32le 2ch 44100Hz
78  1  128  protocol-native.c  float32le 2ch 44100Hz

# Browser connected to correct sink
Sink: 1  ← virtual_sink
application.name = "Chromium"
```

**But transcription still fails** → Audio is routed but content is silence/noise

### 5.3 Root Cause Hypotheses

#### Hypothesis A: Fake Audio Stream Issue
**getUserMedia override (commit 63745d5):**
```javascript
// Created fake AudioContext stream
const audioContext = new AudioContext();
const destination = audioContext.createMediaStreamDestination();
const oscillator = audioContext.createOscillator();
oscillator.connect(destination);
oscillator.start();
return destination.stream;
```

**Result:**
- ✅ Zoom accepted stream (audio join worked)
- ❌ Meeting audio didn't flow through this stream
- **Why:** Fake stream is for microphone input, not speaker output

#### Hypothesis B: WebRTC Audio Output Routing
**WebRTC flow in Zoom:**
```
Remote peer → RTCPeerConnection → Audio output → Browser speaker
                                                         ↓
                                           Should go to: virtual_sink
                                           Actually: ???
```

**Problem:** Even though browser connects to virtual_sink, **meeting audio may not route there**

#### Hypothesis C: PulseAudio Capture Issue
```bash
# Test needed on EC2:
paplay /usr/share/sounds/alsa/Front_Center.wav  # Play test sound
parec --device=virtual_sink.monitor /tmp/test.raw  # Capture

# If test.raw is empty → PulseAudio capture broken
# If test.raw has audio → Zoom audio routing problem
```

## 6. Key Technical Decisions & Commits

### 6.1 Major Fixes Applied

**Commit e9301c8:** Revert to Playwright fill() API
```python
# BROKEN: Direct JS value assignment
inp.value = 'Companion';
inp.dispatchEvent(new Event('input'));

# FIXED: Playwright API (triggers React validation)
await name_input.fill(self.display_name)
```

**Commit 475a61d:** Fix preview page detection
```python
# BROKEN: Mute button present on preview AND meeting
if await page.query_selector('button[aria-label="Mute"]'):

# FIXED: Chat/Participants only in actual meeting
if await page.query_selector('button[aria-label="Chat"]'):
```

**Commit f5934b5:** Click audio toolbar button
```python
# Find lowercase "audio" button (not joined state)
audio_btn = await page.query_selector('button[aria-label="audio"]')
await audio_btn.click()  # Opens join menu
```

**Commit bbadadc:** Cancel stuck auto-join
```python
# Detect "Joining Meeting..." loop
# Click audio button to cancel
# Click Close buttons to dismiss dialogs
```

**Commit 63745d5:** getUserMedia override (WORKED but incomplete)
```javascript
// Override getUserMedia to return fake stream
// Result: Audio join worked, but no meeting audio captured
```

**Commit a043092:** Revert getUserMedia override (CURRENT)
```python
# Removed fake AudioContext
# Back to Chromium --use-fake-ui-for-media-stream
# Result: Audio join fails again
```

### 6.2 Environment Inheritance Fix
```python
# BROKEN: env parameter replaces entire environment
env={"PULSE_SINK": "virtual_sink"}

# FIXED: Inherit + extend
env={
    **dict(os.environ),  # Inherit PULSE_SERVER etc
    "PULSE_SINK": "virtual_sink",
}
```

## 7. Debugging Infrastructure Added

### 7.1 Browser Console Logging
```python
self._page.on("console",
    lambda msg: print(f"[browser console] {msg.type}: {msg.text}"))
```

**Captures:**
- getUserMedia calls
- WebGL errors
- Zoom internal logs

### 7.2 PulseAudio Stream Check
```python
subprocess.run(["pactl", "list", "sink-inputs"])
# Shows if browser is outputting audio
# Shows which sink it's connected to
```

### 7.3 Audio Join State Verification
```python
# Before: Just check if button exists
# After: Verify aria-label changes
#   "audio" → not joined
#   "mute my microphone" → joined successfully
```

## 8. Failed Approaches (Why They Didn't Work)

### 8.1 ❌ Direct `/dev/snd` Mount
```bash
--device /dev/snd:/dev/snd
```
**Why failed:** EC2 cloud instance has no physical sound card

### 8.2 ❌ Fake AudioContext for Output
```javascript
// Tried to fake speaker output
const oscillator = audioContext.createOscillator();
```
**Why failed:** getUserMedia is for INPUT (mic), not OUTPUT (speaker)

### 8.3 ❌ Waiting for "disabled" to Clear
```javascript
if (btn && !btn.classList.contains('disabled')) {
    btn.click();
}
```
**Why failed:** Zoom Join button is clickable even when marked disabled

### 8.4 ❌ Keyboard Shortcuts (Alt+A, Ctrl+Alt+A)
```python
await page.keyboard.press("Alt+a")
```
**Why failed:** Shortcuts don't work when audio menu isn't open

## 9. Current State Summary

### What Works ✅
| Component | Status | Notes |
|-----------|--------|-------|
| Join meeting | ✅ | Playwright stealth successful |
| Name input | ✅ | Using .fill() API |
| Preview page | ✅ | Detects and clicks Join |
| Waiting room | ✅ | Admits correctly |
| PulseAudio setup | ✅ | virtual_sink + monitor working |
| Speaches API | ✅ | Whisper transcription works |
| Browser → PulseAudio | ✅ | Streams visible in sink-inputs |

### What Doesn't Work ❌
| Component | Status | Issue |
|-----------|--------|-------|
| Audio join | ⚠️ | Inconsistent (worked with getUserMedia override) |
| Meeting audio capture | ❌ | Browser outputs audio but parec captures silence |
| Real speech transcription | ❌ | Whisper hallucinates "you" on silence |

## 10. Next Steps for Debugging

### 10.1 PRIORITY: Test PulseAudio Capture
```bash
# On EC2, test if capture fundamentally works:

# Terminal 1:
paplay /usr/share/sounds/alsa/Front_Center.wav

# Terminal 2 (simultaneously):
timeout 5 parec --device=virtual_sink.monitor \
  --format=s16le --rate=16000 --channels=1 \
  /tmp/test_capture.raw

# Check result:
ls -lh /tmp/test_capture.raw
# If 0 bytes → PulseAudio config issue
# If > 0 bytes → Zoom audio routing issue
```

### 10.2 If PulseAudio Works: Fix Zoom Audio Routing

**Option A:** Make getUserMedia return BOTH fake input AND enable real output
```javascript
// Override getUserMedia to:
// 1. Return fake stream for mic input
// 2. Don't interfere with speaker output routing
```

**Option B:** Force browser audio to virtual_sink at WebRTC level
```javascript
// Patch RTCPeerConnection.setSinkId() or similar
```

**Option C:** Use xvfb + real audio loopback
```bash
# Add virtual display + audio loopback
# Browser thinks it has real display + audio devices
```

### 10.3 If PulseAudio Broken: Alternative Capture Methods

**Option A:** ffmpeg capture from PulseAudio
```bash
ffmpeg -f pulse -i virtual_sink.monitor \
  -ac 1 -ar 16000 -f s16le pipe:1
```

**Option B:** GStreamer pipeline
```bash
gst-launch-1.0 pulsesrc device=virtual_sink.monitor ! \
  audioconvert ! audioresample ! \
  audio/x-raw,rate=16000,channels=1 ! filesink location=/tmp/audio.raw
```

**Option C:** Direct ALSA loopback (if PulseAudio bypassed)

## 11. Architecture Alternatives (If Current Approach Fails)

### 11.1 Stay with Playwright but Different Audio Method
- Use browser DevTools Protocol to capture audio
- Record tab audio via Chrome extension
- Use WebRTC getDisplayMedia with audio

---

## Current Blocker Status

**🔴 BLOCKED:** Audio transcription
- Browser joins meeting ✅
- Browser outputs audio to PulseAudio ✅
- parec captures from monitor source ✅
- **BUT:** Captured audio is silence/noise ❌

**Root cause unknown, requires EC2 PulseAudio test (section 10.1)**
