# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zoom Companion is a real-time meeting transcription bot that joins Zoom meetings via Playwright, captures audio, transcribes speech using Whisper (via Speaches), and generates AI summaries using Claude Haiku. The system consists of three main services:

1. **bot/** (Python): Headless Chromium bot that joins Zoom, captures PulseAudio, runs STT pipeline, stores transcripts
2. **api/** (Node.js): REST API serving meeting metadata and segments from SQLite
3. **dashboard/** (Next.js): Web UI for viewing meetings and live transcripts via WebSocket

## Architecture

### Data Flow
Meeting URL → Playwright Bot (joins Zoom) → PulseAudio Virtual Sink → Audio Capture → Speaches (Whisper) → Transcriber → Pipeline (tags speaker from Zoom active speaker) → Storage (SQLite + markdown files) → WebSocket Server (broadcasts to dashboard)

### Key Components

**bot/main.py** is the entry point. It orchestrates:
- `ZoomBot` (playwright_bot.py): joins meetings, scrapes active speaker, sends chat messages
- `AudioCapture` (audio_capture.py): captures audio from PulseAudio virtual sink
- `Transcriber` (transcriber.py): buffers audio chunks and sends to Speaches API
- `TranscriptPipeline` (pipeline.py): orchestrates audio → STT → speaker tagging → segment emission
- `Storage` (storage.py): SQLite for metadata + local markdown files for transcripts
- `TranscriptWSServer` (ws_server.py): broadcasts segments to dashboard in real-time
- `Summarizer` (summarizer.py): generates summaries via Claude Haiku on AWS Bedrock

**api/server.js** wraps the Lambda-style handler (handlers/meetings.js) for local/Docker deployment. The handler uses better-sqlite3 to read the same SQLite database the bot writes to.

**dashboard/** is a Next.js app with Server Components that fetch meetings from the API. It connects to the bot's WebSocket for live transcript updates.

### Storage Pattern
The bot and API share a SQLite database via Docker volume (`bot-data`). The bot writes; the API reads. The bot also writes markdown transcript files to the same volume for easy export/archiving.

### Testing
- Bot tests use pytest with mocking for external services (Speaches, AWS Bedrock)
- API tests use Jest with in-memory SQLite
- Tests mock Playwright browser automation and PulseAudio capture

## Development Commands

### Local Development (CPU mode, no GPU)
```bash
# Start all services (Speaches CPU + API + bot stub)
cd docker
docker compose -f docker-compose.local.yml up -d

# Check logs
docker compose -f docker-compose.local.yml logs -f

# Stop services
docker compose -f docker-compose.local.yml down
```

### Production - GPU Mode
```bash
# Requires NVIDIA GPU and nvidia-container-toolkit
cd docker
docker compose up -d
```

### Production - CPU-Only (AWS t3.medium recommended)
```bash
# Cost-effective deployment without GPU (~$38/mo vs $385/mo GPU)
cd docker
docker compose -f docker-compose.aws-cpu.yml up -d

# Check logs
docker compose -f docker-compose.aws-cpu.yml logs -f

# Monitor services
docker compose -f docker-compose.aws-cpu.yml ps
```

### Bot Development
```bash
cd bot

# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run tests
pytest

# Run a specific test
pytest tests/test_storage.py -v

# Run bot locally (requires Speaches running)
python -m bot.main --meeting-url "https://zoom.us/wc/join/123" --meeting-id "test123"

# Skip AI summary (faster for testing)
python -m bot.main --meeting-url "..." --meeting-id "..." --no-summary
```

### API Development
```bash
cd api

# Install dependencies
npm install

# Run API server
npm start

# Run tests
npm test
```

### Dashboard Development
```bash
cd dashboard

# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build
npm start
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `SPEACHES_URL`: Speaches base URL (default: http://localhost:8000)
- `BOT_WS_PORT`: WebSocket port for live transcript streaming (default: 8765)
- `BOT_NAME`: Display name when joining Zoom (default: "Companion")
- `DB_PATH`: SQLite database path (default: /data/meetings.db)
- `TRANSCRIPT_DIR`: Directory for markdown transcript files (default: /data/transcripts)
- `API_URL`: API base URL for dashboard (default: http://localhost:3001)
- `NEXT_PUBLIC_BOT_WS_URL`: WebSocket URL for dashboard (default: ws://localhost:8765)
- `AWS_REGION`: AWS region for Bedrock (default: eu-central-1)
- `AWS_S3_BUCKET`: S3 bucket for transcript backups (optional)

**AWS credentials**: The bot uses EC2 instance role in production (no keys needed). For local testing with `--no-summary`, AWS is not required.

## Deployment

### EC2 Setup - GPU Mode (g4dn.xlarge)
```bash
# Run as root on fresh Ubuntu 22.04 instance
sudo bash infra/setup.sh
```

This script:
1. Installs NVIDIA drivers + Docker + NVIDIA Container Toolkit
2. Configures PulseAudio virtual sink for Zoom audio capture
3. Clones repo to /opt/zoom-companionship
4. Starts services via docker-compose

**Cost:** ~$385/month (24/7), GPU-accelerated transcription (real-time)

### EC2 Setup - CPU-Only Mode (t3.medium)
```bash
# Run as root on fresh Ubuntu 22.04 instance
sudo bash infra/setup-cpu.sh
```

This script:
1. Installs Docker (no NVIDIA components)
2. Configures PulseAudio virtual sink for Zoom audio capture
3. Clones repo to /opt/zoom-companionship
4. Starts services via docker-compose-aws-cpu.yml

**Cost:** ~$38/month (24/7), CPU transcription (3-5x slower but much cheaper)

**See:** `docs/aws-deployment-cpu.md` for complete step-by-step CPU deployment guide

### PulseAudio Configuration
The bot captures Zoom audio via a PulseAudio virtual sink. The setup scripts create this automatically. The Playwright browser is configured to route audio through this sink, which the bot then captures via `parec`.

### Speaches (Whisper Service)
Uses the ghcr.io/speaches-ai/speaches Docker image:
- Production GPU: `0.9.0-rc.3-cuda` with `Systran/faster-whisper-large-v3-turbo` (real-time)
- Production CPU: `0.9.0-rc.3-cpu` with `Systran/faster-whisper-small` (3-5x slower)
- Local Dev: `0.9.0-rc.3-cpu` with `Systran/faster-whisper-small` (CPU)

The bot sends 2-second audio chunks as WAV files to `/v1/audio/transcriptions`.

**Model Performance:**
- `faster-whisper-large-v3-turbo`: Best accuracy, requires GPU
- `faster-whisper-small`: Good accuracy, works on CPU, slower
- `faster-whisper-tiny`: Fastest on CPU, lower accuracy

## Common Patterns

### Adding a New Bot Test
Tests use mocking to avoid dependencies on external services. See `tests/test_pipeline.py` for a complete example:
- Mock `ZoomBot.get_active_speaker()` to return test speakers
- Mock `AudioCapture.stream()` to yield test audio chunks
- Mock `Transcriber.transcribe_chunk()` to yield test transcript segments

### Adding a New API Endpoint
1. Add route handling to `api/handlers/meetings.js`
2. Use `getDb()` from `api/db.js` for SQLite access
3. Return `{ statusCode, headers, body }` for Lambda-compatible response
4. Add test to `api/tests/meetings.test.js`

### Adding a New Dashboard Page
1. Create page in `dashboard/app/` (Next.js App Router)
2. Use Server Components for data fetching (no client-side fetch needed)
3. Use `process.env.API_URL` to call the API
4. Add client components in `dashboard/components/` when interactivity is needed

## Troubleshooting

### Bot fails to join Zoom
- Check that the meeting URL is in the correct format (https://zoom.us/wc/join/...)
- The bot automatically rewrites `/j/` URLs to `/wc/join/`
- Ensure Playwright browsers are installed: `playwright install chromium`

### No audio captured
- Verify PulseAudio virtual sink is running: `pactl list sinks | grep virtual`
- Check that the bot container has access to the PulseAudio socket (volume mount in docker-compose.yml)
- The PULSE_SERVER environment variable must point to the correct socket

### Transcription is slow or fails
- Check Speaches health: `curl http://localhost:8000/health`
- Verify GPU is available in production: `nvidia-smi` (inside container)
- For CPU mode, use the smaller `faster-whisper-small` model

### Dashboard shows no meetings
- Verify API is running: `curl http://localhost:3001/meetings`
- Check that the bot has written to the SQLite database
- Ensure the api and bot services share the same Docker volume

## File Locations in Production

- Code: `/opt/zoom-companionship/`
- Data: Docker volume `bot-data` (mounted at `/data/` in containers)
  - SQLite: `/data/meetings.db`
  - Transcripts: `/data/transcripts/*.md`
- Logs: `docker compose logs -f` (in `/opt/zoom-companionship/docker/`)

---

## Current Status & Known Issues (Updated: 2026-03-11)

### 🔴 CRITICAL BLOCKER: Audio Join Dialog Detection Failure

**Current State:** Bot successfully joins Zoom meetings and PulseAudio infrastructure works perfectly, but bot cannot click the "Join with computer audio" button in Zoom's audio dialog.

**What Works ✅**
- Bot joins Zoom meetings via Playwright ✅
- Playwright stealth bypasses detection ✅
- PulseAudio virtual_sink created and working ✅
- PulseAudio capture fundamentals verified (159KB/5sec test) ✅
- Speaches API transcribes test audio successfully ✅
- AudioContext state: 'running' (autoplay policy fixed) ✅
- Xvfb virtual display running ✅
- Browser doesn't crash (GPU/WebGL disabled) ✅

**What Doesn't Work ❌**
- **Audio join dialog:** Bot cannot find/click "Join with computer audio" button
- **Result:** No audio streams created in PulseAudio
- **Root cause:** Zoom's audio dialog doesn't match expected selectors, or timing issue

### 📋 Debugging Session Summary (2026-03-11)

**Total Time Invested:** ~5-6 hours of systematic debugging

**Attempts Made:**

1. **Autoplay Policy Fix** (commit 69086d0)
   - Added `--autoplay-policy=no-user-gesture-required`
   - Result: AudioContext now 'running' ✅

2. **GPU/WebGL Disable** (commit 70b8452)
   - Added `--disable-gpu`, `--disable-webgl`, `--disable-dev-shm-usage`
   - Result: Browser crashes fixed ✅

3. **AudioContext Resume** (commit 4759a4c)
   - Explicitly resume AudioContext on page load
   - Result: Confirmed 'running' state ✅

4. **Stuck Detection Removal** (commit 710dd04)
   - Removed complex "Joining Meeting..." detection
   - Result: No improvement, audio streams still not created ❌

5. **Clean Audio Join Logic** (commit 80c47c5)
   - Rewrote audio button clicking with explicit menu search
   - Result: Menu doesn't open after clicking ❌

6. **Hover + JS Click** (commit df2f7e4)
   - Changed to hover + JavaScript click instead of Playwright .click()
   - Increased wait time 2s → 5s
   - Result: Menu still doesn't open ❌

7. **Xvfb Virtual Display** (commit 30f9699)
   - Added X Virtual Framebuffer for proper UI rendering
   - Result: Browser has display but audio join still fails ❌

8. **Dialog-First Approach** (commit d398417)
   - Based on manual screenshot analysis
   - Search for "Join with computer audio" button BEFORE dismissing dialog
   - Result: Button not found in DOM ❌

**Key Diagnostics:**
```bash
# PulseAudio test (SUCCESS):
- Capture test: 159KB/5sec ✅
- virtual_sink: RUNNING ✅
- Browser streams when working: 2-3 streams visible ✅

# Current state (FAILURE):
- Button count after audio click: 15 (unchanged)
- No audio menu appears
- No Chromium streams in PulseAudio
- "Join with computer audio" button not found in DOM
```

### 📋 Detailed Technical Status

#### ✅ Infrastructure (AWS EC2 t3.medium CPU-Only)
- EC2 instance running Ubuntu 22.04
- Speaches API: Port 8000 (CPU mode, `faster-whisper-small`)
- API Server: Port 3001, externally accessible
- Docker containers running successfully
- SQLite database initialized
- PulseAudio configured with virtual_sink
- IAM role configured for AWS Bedrock
- Security groups: Ports 22, 8000, 3001, 8765 open
- **Cost:** ~$38/month (24/7)

#### ✅ Bot Join Flow (Working)
- Playwright + playwright-stealth successfully loads Zoom web client
- Name input filled via `.fill()` API
- Join button clicked successfully
- Waiting room detection working
- Bot appears in participants list as "Companion"

#### ❌ Audio Pipeline (Broken)
**Evidence from latest runs:**
```
[bot] ✓ Browser audio stream found in PulseAudio!
[bot]   Sink: 1  ← virtual_sink (correct)
[bot]   application.name = "Chromium"
```
**BUT:** parec captures silence → Whisper outputs "you" repeatedly

**Hypotheses:**
1. **WebRTC routing issue:** Meeting audio doesn't route through browser's default output
2. **PulseAudio capture issue:** virtual_sink.monitor not capturing properly
3. **Fake audio stream:** Previous getUserMedia override may have interfered

#### ⚠️ Minor Issues
- Admission detection may fire prematurely (needs button label verification)
- Speaker detection returns "Unknown" (low priority until audio works)

### 🔍 Next Debugging Steps (Priority Order)

#### Step 1: Test PulseAudio Capture Fundamentals
```bash
# On EC2, verify if PulseAudio capture works at all:

# Terminal 1: Play test sound
paplay /usr/share/sounds/alsa/Front_Center.wav

# Terminal 2: Simultaneously capture
timeout 5 parec --device=virtual_sink.monitor \
  --format=s16le --rate=16000 --channels=1 \
  /tmp/test_capture.raw

# Check result:
ls -lh /tmp/test_capture.raw
# If 0 bytes → PulseAudio config issue
# If > 0 bytes → Zoom audio routing issue
```

#### Step 2: If PulseAudio Works, Fix Zoom Audio Routing
**Option A:** Force browser audio sink
```python
# In playwright_bot.py, set PULSE_SINK env var:
env = {
    **dict(os.environ),
    "PULSE_SINK": "virtual_sink",
}
```

**Option B:** Patch WebRTC setSinkId
```javascript
// Override RTCPeerConnection audio output routing
RTCPeerConnection.prototype.setSinkId = async function(sinkId) {
    console.log('Audio routed to:', sinkId);
};
```

**Option C:** Use xvfb + audio loopback
```bash
# Add virtual display + audio loopback
# Browser thinks it has real display + audio devices
```

#### Step 3: Alternative Capture Methods
If PulseAudio fundamentally broken:
- **ffmpeg:** `ffmpeg -f pulse -i virtual_sink.monitor -ac 1 -ar 16000 -f s16le pipe:1`
- **GStreamer:** `gst-launch-1.0 pulsesrc device=virtual_sink.monitor ! audioconvert ! ...`
- **Direct ALSA loopback** (bypass PulseAudio)

### 📍 Current EC2 State
- Location: `/opt/zoom-companionship/`
- PulseAudio: virtual_sink (sink id 1, s16le 2ch 44100Hz SUSPENDED)
- Speaches: running on port 8000
- API: running on port 3001
- Bot Docker image: `zoom-bot`
- PulseAudio socket: `/run/user/1000/pulse/native`

### 🏃 EC2 Run Command (Latest)
```bash
# From /opt/zoom-companionship/bot:
chmod 777 /run/user/1000/pulse && chmod 777 /run/user/1000/pulse/native
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

### 🔄 Alternative Architecture Options (If Audio Routing Unfixable)

#### Option 1: Browser DevTools Protocol Audio Capture
Use Chrome DevTools Protocol to capture tab audio directly:
- More direct access to browser audio streams
- Bypasses PulseAudio complexity
- May require chromium instead of playwright-chromium

#### Option 2: Chrome Extension for Audio Recording
Create Chrome extension to capture tab audio:
- Access to tabCapture API
- More reliable than PulseAudio routing
- Requires packaged extension deployment

#### Option 3: WebRTC getDisplayMedia with Audio
Use screen sharing API to capture audio:
```javascript
navigator.mediaDevices.getDisplayMedia({
  video: false,
  audio: true
})
```
- Official API for capturing tab audio
- May require user interaction (not suitable for headless)

#### Option 4: Third-Party Meeting Bot Services (Fastest Solution)
Use commercial APIs to bypass all technical challenges:
- **Recall.ai** - ~$0.10/meeting minute (~$6/hour)
- **Assembly.ai** - Real-time transcription
- **Fireflies.ai** - Full meeting bot service
- ✅ Guaranteed to work immediately
- ❌ Monthly cost (~$20-50/mo base + usage)
- ❌ Less control, vendor lock-in

#### Option 5: Zoom Meeting SDK (Official but Complex)
Switch to Zoom's official SDK:
- ✅ No detection, officially supported
- ❌ Requires Zoom Marketplace app approval
- ❌ OAuth flow complexity
- ❌ Major architecture change

### 🎯 Next Steps (Updated 2026-03-11)

**Immediate Decision Required:**

Given 5+ hours of debugging with no audio join success, three paths forward:

**Option A: Continue Custom Bot (High Risk)**
- Debug why "Join with computer audio" button not found
- Estimated time: 3-5 more hours, no guarantee of success
- Technical debt: Fragile UI scraping, breaks when Zoom updates

**Option B: Third-Party Bot Service (Recommended)** ⭐
- **Recall.ai**: $0.10/min (~$6/hour meeting)
- Integration time: 1-2 hours
- Success rate: 100% guaranteed
- Trade-off: Monthly cost (~$60 for 10 hours) vs development time

**Option C: Zoom Meeting SDK (Official)**
- Requires Zoom Marketplace app approval
- OAuth flow complexity
- Estimated time: 1 week+
- Benefit: Official API, no detection issues

**Cost Comparison:**
```
Custom Bot: $38/mo (EC2) + 50+ dev hours
Recall.ai:  $60/mo (10 hours) + 2 dev hours
```

**Recommendation:** Evaluate Recall.ai for MVP. Custom bot can be revisited later if cost becomes prohibitive.

**Priority 2: Once Audio Works (Whichever Path)**
1. Test full end-to-end workflow (join → transcribe → save → display)
2. Fix speaker detection selectors
3. Test WebSocket streaming to dashboard
4. Verify summary generation with AWS Bedrock

**Priority 3: Production Hardening**
1. Deploy dashboard (Next.js on Vercel or EC2)
2. Add authentication to dashboard
3. Implement S3 transcript backup
4. Add CloudWatch monitoring and alarms
5. SSL/HTTPS with Let's Encrypt
6. Assign Elastic IP to EC2

### 📝 Technical Debt

1. **Audio routing:** CRITICAL - blocking all functionality
2. **Speaker detection:** Selectors outdated, returns "Unknown"
3. **Dashboard:** Not deployed, only API accessible
4. **Monitoring:** No alerts or health checks
5. **Backup:** S3 integration exists but not enabled
6. **Security:** No HTTPS, no dashboard auth
7. **Documentation:** Needs troubleshooting runbook

### 📊 Testing Status

**✅ Working Components:**
- Speaches API (model loading, health endpoint, transcription)
- API server (endpoints, SQLite reads)
- SQLite database (initialization, writes, reads)
- Docker networking (container-to-container)
- External access (API publicly accessible)
- Bot join flow (Playwright, stealth, Zoom web client load)
- Name input and button clicking
- Waiting room detection
- PulseAudio connection (browser → PulseAudio established)

**❌ Broken Components:**
- **Audio routing** (meeting audio not captured, only silence/noise)
- Speaker detection (selectors outdated, returns "Unknown")

**⏳ Not Yet Tested:**
- End-to-end workflow (blocked by audio routing)
- WebSocket streaming (blocked by audio routing)
- Meeting summary generation (blocked by audio routing)
- Dashboard deployment
- Multiple concurrent meetings
- Long-running meeting stability

### 🐛 Known Issues

1. **CRITICAL: Audio routing** - Meeting audio not captured, only silence/noise
   - Browser connects to PulseAudio but WebRTC audio doesn't route through virtual_sink
   - See Priority 1 in Action Plan above

2. **Speaker detection broken** - Returns "Unknown" for all speakers
   - Zoom UI selectors outdated
   - Low priority until audio routing fixed

3. **docker-compose.local.yml** - Has obsolete `version` attribute (warnings only, not critical)

### 📚 Documentation

**Complete:**
- ✅ `CLAUDE.md` - Project instructions (this file)
- ✅ `docs/architecture-current-status.md` - Complete architecture and current blocker details
- ✅ `docs/aws-deployment-cpu.md` - CPU deployment guide
- ✅ `docs/aws-deployment-guide.md` - GPU deployment guide
- ✅ `docker/docker-compose.aws-cpu.yml` - CPU deployment config
- ✅ `infra/setup-cpu.sh` - Automated setup script

**Needs Creation:**
- ⏳ Audio troubleshooting runbook
- ⏳ Dashboard deployment guide
- ⏳ API documentation
- ⏳ WebSocket protocol spec

### 🔐 Security Considerations

**Currently Implemented:**
- EC2 IAM role for AWS credentials (no hardcoded keys)
- Security groups restrict access to necessary ports only
- `.env` file for configuration (not committed to git)

**Still Needed:**
- HTTPS/SSL for API and dashboard
- Authentication for dashboard access
- Rate limiting on API endpoints
- Input validation for meeting URLs
- Secrets management for production
- Regular security updates for dependencies

### 💰 Cost Breakdown (AWS t3.medium CPU Deployment)

**Monthly Costs (24/7 operation):**
- EC2 t3.medium: ~$35/month
- EBS 30GB gp3: ~$3/month
- Data transfer: ~$1/month (minimal)
- **Total: ~$38/month**

**Per-Meeting Costs (if using on-demand):**
- EC2 hourly: $0.048/hour
- 1-hour meeting: ~$0.05
- 10 meetings/month: ~$6/month (including startup overhead)

**Additional Costs (if needed):**
- AWS Bedrock (Claude Haiku): ~$0.01/meeting summary
- S3 storage: ~$0.023/GB/month
- Elastic IP: $0 (if in use), $3.65/month (if not attached)

---

**Last Updated:** 2026-03-11
**Status:** Audio join dialog detection blocked - bot joins meeting successfully, PulseAudio verified working, but cannot trigger Zoom's audio join
**Next Action:** Decide between continuing custom bot debugging vs. third-party service (Recall.ai)
**Latest Commit:** 734234a (debug logging for button detection)
