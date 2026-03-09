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
