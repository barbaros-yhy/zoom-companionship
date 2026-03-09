# Zoom RTMS Bot

Real-time meeting transcription bot using Zoom's official Real-Time Meeting Service (RTMS) SDK.

## Overview

This bot replaces the Playwright-based scraping approach with Zoom's official RTMS SDK, which provides:

- Official Zoom API integration (no web scraping or bot detection issues)
- Real-time transcript streaming via webhooks
- Speaker identification built-in
- More reliable and maintainable architecture

## Architecture

The bot consists of:

1. **Webhook Server**: Express server to receive RTMS transcript events
2. **Storage**: SQLite database for meeting metadata and segments
3. **WebSocket Server**: Broadcasts live transcripts to dashboard
4. **Summarizer**: Generates AI summaries using AWS Bedrock (Claude Haiku)

## Prerequisites

- Node.js 18+ with ES modules support
- Zoom RTMS credentials (OAuth app in Zoom Marketplace)
- AWS credentials for Bedrock (optional, for summaries)

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
# Zoom RTMS Configuration
ZOOM_CLIENT_ID=your_client_id
ZOOM_CLIENT_SECRET=your_client_secret
ZOOM_WEBHOOK_SECRET=your_webhook_secret

# Server Configuration
PORT=3000
WS_PORT=8765

# Database
DB_PATH=/data/meetings.db
TRANSCRIPT_DIR=/data/transcripts

# AWS (optional, for summaries)
AWS_REGION=eu-central-1
```

### 3. Build

```bash
npm run build
```

### 4. Run

```bash
# Production
npm start

# Development (with auto-reload)
npm run dev
```

## Development

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch
```

### Project Structure

```
bot-rtms/
├── src/
│   ├── index.ts          # Entry point
│   ├── webhook.ts        # Webhook server for RTMS events
│   ├── storage.ts        # SQLite storage layer
│   ├── ws-server.ts      # WebSocket server for live updates
│   ├── summarizer.ts     # AI summary generation
│   └── types.ts          # TypeScript type definitions
├── package.json
├── tsconfig.json
└── jest.config.js
```

## Zoom RTMS Setup

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/)
2. Create a new "RTMS App"
3. Enable "Real-Time Meeting Service" feature
4. Configure webhook endpoint: `https://your-domain.com/webhook/rtms`
5. Copy Client ID, Client Secret, and Webhook Secret to `.env`

## Deployment

See `docs/rtms-deployment.md` for production deployment instructions.

## Migration from Playwright Bot

This bot replaces the Python Playwright bot (`bot/`). Key differences:

- **No browser automation**: Uses official Zoom API
- **No audio capture**: Zoom provides transcripts directly
- **No Whisper/Speaches**: Zoom handles transcription
- **Webhook-based**: Bot receives events via HTTP, not WebSocket
- **TypeScript**: Modern Node.js with ES modules

## Troubleshooting

### Webhook not receiving events

- Verify webhook URL is publicly accessible
- Check Zoom app configuration has correct endpoint
- Ensure webhook secret matches `.env` configuration
- Check logs for signature verification errors

### Database errors

- Ensure DB_PATH directory exists and is writable
- Check SQLite version compatibility
- Verify no other process has locked the database

## License

ISC
