# Zoom Companionship

A real-time meeting transcription and summarization system for Zoom meetings.

## Architecture (Updated 2026-03-09)

### RTMS Bot (bot-rtms/)

The bot uses Zoom's official RTMS SDK instead of web scraping:

- **Webhook-based:** Zoom sends `meeting.rtms_started` events
- **Official SDK:** No detection issues, fully supported
- **Direct transcripts:** No audio processing needed
- **Concurrent meetings:** Multiple meetings supported simultaneously
- **Cost-effective:** Runs on t3.small (~$18/month vs $385/month GPU)

See `bot-rtms/DEPLOYMENT.md` for setup instructions.

### Old Bot (Deprecated)

The Python bot in `bot/` is deprecated due to Zoom detection issues. It is kept for reference but should not be used.

## Services

1. **bot-rtms/** (TypeScript): RTMS-based bot that receives Zoom transcripts via webhook and official SDK
2. **api/** (Node.js): REST API serving meeting metadata and segments from SQLite
3. **dashboard/** (Next.js): Web UI for viewing meetings and live transcripts via WebSocket

## Quick Start

### Local Development

```bash
# Start API and dashboard
cd docker
docker compose -f docker-compose.local.yml up -d

# Start RTMS bot
cd bot-rtms
npm install
cp .env.example .env
npm run dev
```

### Production Deployment

See `bot-rtms/DEPLOYMENT.md` for full production setup instructions.

```bash
# On EC2 instance
export ZM_RTMS_CLIENT=your_client_id
export ZM_RTMS_SECRET=your_client_secret
sudo -E ./infra/setup-rtms.sh
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ZM_RTMS_CLIENT` | Zoom app client ID | required |
| `ZM_RTMS_SECRET` | Zoom app client secret | required |
| `WEBHOOK_PORT` | Webhook listener port | 8080 |
| `BOT_WS_PORT` | WebSocket port for dashboard | 8765 |
| `DB_PATH` | SQLite database path | /data/meetings.db |
| `TRANSCRIPT_DIR` | Markdown transcript directory | /data/transcripts |
| `AWS_REGION` | AWS region for Bedrock | eu-central-1 |

## Cost

- **RTMS bot on t3.small:** ~$18/month (24/7)
- **AWS Bedrock (Claude Haiku):** ~$0.01/meeting summary

## Documentation

- `bot-rtms/DEPLOYMENT.md` - RTMS bot deployment guide
- `docs/aws-deployment-cpu.md` - CPU deployment guide
- `docs/plans/` - Architecture and implementation plans
- `CLAUDE.md` - Developer context and project status
