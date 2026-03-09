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

## Current Status & Known Issues (Updated: 2026-03-09)

### ✅ Successfully Deployed Components

**AWS EC2 CPU-Only Deployment (t3.medium) - WORKING:**
- ✅ EC2 instance: `t3.medium` running Ubuntu 22.04
- ✅ Speaches API: Running healthy on port 8000 (CPU mode with `faster-whisper-small` model)
- ✅ API Server: Running healthy on port 3001, accessible externally
- ✅ Docker containers: Built and running successfully
- ✅ SQLite database: Initialized and shared between containers
- ✅ PulseAudio: Installed (but not verified working with Zoom)
- ✅ External access: API endpoint tested and responding correctly (`[]` from `/meetings`)
- ✅ IAM role: Configured for AWS Bedrock access (for summary generation)
- ✅ Security groups: Ports 22, 8000, 3001, 8765 open

**Cost:** ~$38/month (24/7) or ~$6/month (4 hours/day usage)

**Deployment Process Used:**
1. Made repository public on GitHub
2. Created `docker/docker-compose.aws-cpu.yml` for CPU-only deployment
3. Created `infra/setup-cpu.sh` automated setup script
4. Manually executed setup steps (script failed due to GitHub raw URL cache issue)
5. Services started successfully with `docker compose -f docker-compose.aws-cpu.yml up -d`

### ❌ CRITICAL BLOCKER: Zoom Web Client Bot Detection

**Issue:** The Playwright-based bot cannot join Zoom meetings via web client.

**Symptoms:**
- Bot logs show "Joined: [URL]" but bot never appears in Zoom participants list
- Playwright successfully opens Zoom URL but cannot find join UI elements
- Page title: "Zoom meeting on web" but content shows browser detection errors

**Root Cause Analysis:**
```
Page Content Analysis:
- ERROR: Browser not supported message!
- ERROR: Download app message!
- Current URL redirects to: https://app.zoom.us/wc/[ID]/join?_x_zm_rtaid=...
- Name input selector: NOT FOUND
- Join button selector: NOT FOUND
```

**Zoom's Detection Mechanisms:**
1. Detects `navigator.webdriver === true` (Playwright/Puppeteer signature)
2. Checks for automation-controlled browser flags
3. Analyzes browser fingerprint (missing plugins, unusual behavior)
4. Shows "Browser not supported" page and forces app download

**Attempted Solutions (All Failed):**
1. ❌ Added `--disable-blink-features=AutomationControlled` flag
2. ❌ Added `--disable-dev-shm-usage` flag
3. ❌ Added `--disable-features=IsolateOrigins,site-per-process` flag
4. ❌ Tried both `/j/` and `/wc/join/` URL formats
5. ❌ Tested with and without meeting passwords

**Current Bot Code Location:** `bot/playwright_bot.py` lines 36-45 (browser launch configuration)

### 🔧 Potential Solutions (Not Yet Implemented)

#### Option 1: Advanced Anti-Detection (Medium Effort)
Add JavaScript injection to mask automation:
```python
await page.evaluate("""
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
""")
```
Location: After `new_page()` in `playwright_bot.py:54`

**Success Rate:** ~40% (Zoom actively fights this)

#### Option 2: Use Zoom Meeting SDK (High Effort, Recommended)
Switch from web scraping to official Zoom Meeting SDK:
- ✅ Officially supported by Zoom
- ✅ No detection issues
- ❌ Requires Zoom Marketplace App registration
- ❌ Requires OAuth credentials
- ❌ More complex setup
- ❌ Significant code refactoring needed

**Documentation:** https://developers.zoom.us/docs/meeting-sdk/

#### Option 3: Use Puppeteer-Extra with Stealth Plugin (Medium Effort)
Replace Playwright with `puppeteer-extra-plugin-stealth`:
- Switch from Python Playwright to Node.js Puppeteer
- Uses evasion techniques specifically for headless detection
- Better success rate with modern detection systems
- ❌ Requires rewriting bot in JavaScript/TypeScript

#### Option 4: Third-Party Meeting Bot Services (Easy, Paid)
Use commercial meeting bot APIs:
- **Recall.ai** - API to send bots to meetings (~$0.10/meeting minute)
- **Assembly.ai** - Real-time transcription API
- **Fireflies.ai** - Meeting bot as a service
- ✅ Guaranteed to work
- ❌ Monthly subscription required
- ❌ Less control over bot behavior

#### Option 5: Zoom Phone/Zoom Rooms API (Alternative Approach)
Use Zoom Phone to dial into meeting as audio participant:
- Avoids web client detection entirely
- Works like a phone dial-in
- ❌ Requires Zoom Phone license
- ❌ Different API integration

### 📝 Technical Debt & TODOs

1. **Bot Anti-Detection:** Implement navigator.webdriver masking (Option 1)
2. **Bot Alternative:** Research Zoom Meeting SDK migration path (Option 2)
3. **Dashboard:** Deploy Next.js dashboard (currently not deployed)
4. **Monitoring:** Add CloudWatch alarms for service health
5. **Backup:** Implement S3 transcript backup (env var exists but not used)
6. **SSL/HTTPS:** Add nginx reverse proxy with Let's Encrypt
7. **Elastic IP:** Assign static IP to EC2 instance
8. **Docker Compose Version Warning:** Remove obsolete `version` attribute from YAML files

### 🎯 Recommended Next Steps

**Immediate (Unblock Bot):**
1. Try Option 1 (navigator.webdriver masking) - 30 minutes
2. If fails, research Option 2 (Zoom SDK) - understand scope/effort
3. Consider Option 4 (Recall.ai trial) - prove end-to-end system works

**Short-term (Complete MVP):**
1. Get bot successfully joining meetings (any method)
2. Verify audio capture and transcription pipeline
3. Test WebSocket streaming to dashboard
4. Deploy dashboard to EC2 or Vercel
5. Test full workflow: join → transcribe → save → display

**Long-term (Production-Ready):**
1. Migrate to Zoom Meeting SDK (if web scraping remains unreliable)
2. Add authentication to dashboard
3. Implement S3 backup for transcripts
4. Add monitoring and alerting
5. Document production deployment process
6. Create automated deployment scripts

### 📊 Testing Status

**Tested & Working:**
- ✅ Speaches model download and loading
- ✅ Speaches health endpoint
- ✅ API server endpoints
- ✅ SQLite database initialization
- ✅ Docker networking between containers
- ✅ External access to services

**Tested & NOT Working:**
- ❌ Bot joining Zoom meetings
- ⚠️ Audio capture (not tested due to bot join failure)
- ⚠️ Transcription pipeline (not tested due to bot join failure)
- ⚠️ WebSocket streaming (not tested due to bot join failure)
- ⚠️ Meeting summary generation (not tested due to bot join failure)

**Not Yet Tested:**
- ⏳ Dashboard deployment
- ⏳ End-to-end workflow
- ⏳ Multiple concurrent meetings
- ⏳ Long-running meeting stability
- ⏳ PulseAudio audio capture in production

### 🐛 Known Bugs

1. **docker-compose.aws-cpu.yml:** `version` attribute is obsolete, generates warnings
2. **Bot container:** Originally configured with `restart: unless-stopped` and command args, causing infinite restart loop
   - **Fix applied:** Changed to `restart: "no"` and commented out command
3. **GitHub raw URL:** `infra/setup-cpu.sh` returns 404 immediately after push (CDN cache issue)
   - **Workaround:** Manual setup or wait ~5 minutes for CDN propagation

### 📚 Documentation Status

**Created:**
- ✅ `CLAUDE.md` - This file
- ✅ `docs/aws-deployment-cpu.md` - Step-by-step CPU deployment guide
- ✅ `docs/aws-deployment-guide.md` - GPU deployment guide
- ✅ `docker/docker-compose.aws-cpu.yml` - CPU deployment config
- ✅ `infra/setup-cpu.sh` - Automated setup script

**Needs Creation:**
- ⏳ Zoom SDK migration guide
- ⏳ Dashboard deployment guide
- ⏳ Troubleshooting runbook
- ⏳ API documentation
- ⏳ WebSocket protocol documentation

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

**Last Updated:** 2026-03-09 by Claude (Sonnet 4.5)
**Next Agent:** Should focus on solving Zoom web client detection issue (see Option 1-5 above)
