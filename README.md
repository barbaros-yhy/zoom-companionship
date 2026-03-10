# Zoom Companionship

A real-time meeting transcription and summarization system for Zoom meetings.

## Architecture

The system uses Playwright to join Zoom meetings via headless Chromium, captures audio via PulseAudio, transcribes with Speaches (Whisper), and stores transcripts in SQLite + markdown files.

```
Zoom Meeting → Playwright Bot (Python) → PulseAudio → Audio Capture
                                                          ↓
                                                    Speaches (Whisper)
                                                          ↓
                                                     Transcriber
                                                          ↓
                                                    SQLite + Files
                                                          ↓
                                                    WebSocket Server
                                                          ↓
                                                      Dashboard
```

## Services

1. **bot/** (Python): Playwright-based bot that joins Zoom, captures audio, transcribes via Speaches
2. **api/** (Node.js): REST API serving meeting metadata and segments from SQLite
3. **dashboard/** (Next.js): Web UI for viewing meetings and live transcripts via WebSocket

## Quick Start

### Local Development

```bash
# Start all services (Speaches CPU + API + bot stub)
cd docker
docker compose -f docker-compose.local.yml up -d
```

### Production Deployment (CPU-Only)

See `docs/aws-deployment-cpu.md` for full deployment instructions.

```bash
# On EC2 t3.medium instance
sudo bash infra/setup-cpu.sh
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SPEACHES_URL` | Speaches API endpoint | http://localhost:8000 |
| `BOT_WS_PORT` | WebSocket port for dashboard | 8765 |
| `BOT_NAME` | Display name when joining Zoom | Companion |
| `DB_PATH` | SQLite database path | /data/meetings.db |
| `TRANSCRIPT_DIR` | Markdown transcript directory | /data/transcripts |
| `AWS_REGION` | AWS region for Bedrock | eu-central-1 |

## Cost (AWS t3.medium CPU Deployment)

- **EC2 t3.medium:** ~$35/month (24/7)
- **EBS storage:** ~$3/month
- **AWS Bedrock (Claude Haiku):** ~$0.01/meeting summary
- **Total:** ~$38/month

## Documentation

- `docs/architecture-current-status.md` - Complete architecture and current status
- `docs/aws-deployment-cpu.md` - CPU deployment guide
- `CLAUDE.md` - Developer context and project instructions
