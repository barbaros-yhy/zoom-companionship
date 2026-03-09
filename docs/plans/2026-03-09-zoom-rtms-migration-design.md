# Zoom RTMS SDK Migration Design

**Date:** 2026-03-09
**Status:** Approved
**Author:** Claude (Sonnet 4.5)

## Executive Summary

Migrate from Playwright-based web scraping bot to Zoom's official RTMS (Realtime Media Streams) SDK. This solves the critical blocker where Zoom detects and blocks the current bot, while significantly reducing system complexity and operational costs.

**Key Benefits:**
- ✅ Solves Zoom detection issue permanently (official SDK)
- ✅ Reduces monthly cost from $385 to $18 (no GPU needed)
- ✅ Eliminates Speaches dependency
- ✅ Eliminates PulseAudio complexity
- ✅ Direct transcript access (no audio processing needed)
- ✅ More reliable and maintainable

## Problem Statement

Current system uses Playwright to join Zoom meetings via web client. Zoom actively detects and blocks headless browsers with:
- `navigator.webdriver` detection
- Browser fingerprinting
- Automation-controlled flags

This makes the bot unreliable and unmaintainable. Multiple workarounds have failed.

## Solution: Zoom RTMS SDK

Use Zoom's official Realtime Media Streams SDK which provides:
- Webhook-based meeting join (no web scraping)
- Direct transcript stream access
- Real-time audio/video streams (if needed in future)
- Per-participant speaker attribution
- Session lifecycle management
- Production-ready error handling

## Architecture

### Current Architecture (Deprecated)

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

### New Architecture (RTMS-based)

```
Zoom Meeting → meeting.rtms_started webhook → RTMS Bot (Node.js/TypeScript)
                                                    ↓
                                        RTMS Client Manager (concurrent meetings)
                                                    ↓
                                        onTranscriptData callback
                                                    ↓
                                    Storage (SQLite + markdown files)
                                                    ↓
                                        WebSocket Server (live broadcast)
                                                    ↓
                                            Dashboard (unchanged)
```

### Components Removed

- ❌ **Python bot** (`bot/` directory) - replaced with Node.js bot
- ❌ **Speaches service** - transcript comes directly from Zoom
- ❌ **PulseAudio setup** - no audio capture needed
- ❌ **AudioCapture module** - not needed
- ❌ **Transcriber module** - not needed
- ❌ **Playwright dependency** - not needed

### Components Preserved

- ✅ **API** (`api/`) - unchanged, still reads from SQLite
- ✅ **Dashboard** (`dashboard/`) - unchanged, same WebSocket protocol
- ✅ **SQLite schema** - unchanged, same tables and columns
- ✅ **Markdown transcript format** - unchanged

### New Components

**bot-rtms/** (Node.js/TypeScript):
```
bot-rtms/
├── src/
│   ├── index.ts                 # Entry point, webhook server
│   ├── rtms-client-manager.ts   # Manages multiple concurrent meetings
│   ├── storage.ts               # SQLite + markdown writer (ported from Python)
│   ├── websocket-server.ts     # Live transcript broadcast (ported from Python)
│   ├── summarizer.ts            # AWS Bedrock integration (ported from Python)
│   └── types.ts                 # TypeScript type definitions
├── package.json
├── tsconfig.json
└── Dockerfile
```

## Data Flow

### 1. Webhook Flow (Meeting Start)

```
1. User starts Zoom meeting with RTMS enabled
2. Zoom → POST /webhook { event: "meeting.rtms_started", payload: {...} }
3. Webhook handler validates signature
4. ClientManager.createClient(meetingId, payload)
5. RTMS Client.join(payload) → connects to Zoom WebSocket
6. onJoinConfirm callback triggered
7. Storage.createMeeting(meetingId, metadata)
```

### 2. Transcript Flow (During Meeting)

```
1. Participant speaks in Zoom
2. Zoom → onTranscriptData(buffer, timestamp, metadata)
3. Parse transcript: {
     text: buffer.toString('utf-8'),
     speaker: metadata.userName,
     userId: metadata.userId,
     timestamp: timestamp
   }
4. Storage.saveSegment(meetingId, segment)
5. WebSocketServer.broadcast(meetingId, segment)
6. Dashboard receives update and displays in real-time
```

### 3. Meeting End Flow

```
1. Meeting ends → RTMS onLeave(reason) callback
2. Storage.finalizeMeeting(meetingId)
3. Summarizer.generate(meetingId) → calls AWS Bedrock (Claude Haiku)
4. Storage.saveSummary(meetingId, summary)
5. ClientManager.removeClient(meetingId)
6. Memory cleanup and connection closure
```

### 4. Concurrent Meetings

```
Meeting A: webhook → clientA → transcriptA → storageA
Meeting B: webhook → clientB → transcriptB → storageB
```

- Each meeting has its own RTMS Client instance
- Stored in `Map<meetingId, ClientInstance>`
- SQLite writes are serialized (better-sqlite3 is thread-safe)
- WebSocket broadcasts are filtered by meeting ID
- Memory cleanup on meeting end prevents leaks

## Technical Details

### Technology Stack

**Runtime & Language:**
- Node.js 20+
- TypeScript 5.x

**Dependencies:**
- `@zoom/rtms` - Official Zoom RTMS SDK
- `better-sqlite3` - Synchronous, thread-safe SQLite
- `ws` - WebSocket server
- `@aws-sdk/client-bedrock-runtime` - AWS Bedrock for summaries

**Infrastructure:**
- Docker container (single service)
- Ubuntu 22.04
- EC2 t3.small (~$18/month)
- nginx + Let's Encrypt for SSL

### Environment Variables

**New variables:**
```env
ZM_RTMS_CLIENT=<zoom_client_id>
ZM_RTMS_SECRET=<zoom_client_secret>
ZM_RTMS_PORT=8080
ZM_RTMS_PATH=/webhook
```

**Existing variables (unchanged):**
```env
BOT_WS_PORT=8765
DB_PATH=/data/meetings.db
TRANSCRIPT_DIR=/data/transcripts
AWS_REGION=eu-central-1
BOT_NAME=Companion
```

**Removed variables:**
```env
SPEACHES_URL (not needed)
```

### RTMS Client Manager

```typescript
class RTMSClientManager {
  private clients: Map<string, RTMSClientInstance>;

  createClient(meetingId: string, payload: RTMSPayload) {
    const client = new rtms.Client();

    client.onJoinConfirm((reason) => {
      this.handleJoinConfirm(meetingId, reason);
    });

    client.onTranscriptData((data, timestamp, metadata) => {
      this.handleTranscript(meetingId, data, timestamp, metadata);
    });

    client.onParticipantEvent((event, timestamp, participants) => {
      this.handleParticipants(meetingId, event, participants);
    });

    client.onLeave((reason) => {
      this.handleLeave(meetingId, reason);
    });

    client.join(payload);
    this.clients.set(meetingId, { client, startTime: Date.now() });
  }

  removeClient(meetingId: string) {
    const instance = this.clients.get(meetingId);
    if (instance) {
      instance.client.leave();
      this.clients.delete(meetingId);
    }
  }
}
```

### Storage Layer

Port existing Python `storage.py` to TypeScript with same schema:

**Tables (unchanged):**
```sql
CREATE TABLE meetings (
  id TEXT PRIMARY KEY,
  title TEXT,
  start_time INTEGER,
  end_time INTEGER,
  status TEXT,
  summary TEXT
);

CREATE TABLE segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  meeting_id TEXT,
  speaker TEXT,
  text TEXT,
  timestamp INTEGER,
  FOREIGN KEY (meeting_id) REFERENCES meetings(id)
);
```

**Markdown format (unchanged):**
```markdown
# Meeting: [meeting_id]
Date: [date]
Duration: [duration]

## Summary
[AI-generated summary]

## Transcript
**[Speaker Name]** ([timestamp]): [text]
**[Speaker Name]** ([timestamp]): [text]
...
```

### WebSocket Server

Port existing Python `ws_server.py` to TypeScript:

**Message format (unchanged):**
```json
{
  "type": "segment",
  "meeting_id": "abc123",
  "segment": {
    "speaker": "John Doe",
    "text": "Hello everyone",
    "timestamp": 1234567890
  }
}
```

Dashboard client code needs no changes.

### Summarizer

Port existing Python `summarizer.py` to TypeScript:

```typescript
import { BedrockRuntimeClient, InvokeModelCommand } from "@aws-sdk/client-bedrock-runtime";

async function generateSummary(meetingId: string): Promise<string> {
  const segments = storage.getSegments(meetingId);
  const transcript = formatTranscript(segments);

  const client = new BedrockRuntimeClient({ region: process.env.AWS_REGION });
  const command = new InvokeModelCommand({
    modelId: "anthropic.claude-haiku-20240307-v1:0",
    body: JSON.stringify({
      anthropic_version: "bedrock-2023-05-31",
      messages: [{
        role: "user",
        content: `Summarize this meeting transcript:\n\n${transcript}`
      }],
      max_tokens: 2000,
      temperature: 0.7
    })
  });

  const response = await client.send(command);
  const result = JSON.parse(new TextDecoder().decode(response.body));
  return result.content[0].text;
}
```

## Zoom Marketplace Setup

### App Configuration

1. **Create Zoom Account-level OAuth App:**
   - Go to https://marketplace.zoom.us/develop/create
   - Select "Account-level app"
   - Enable RTMS feature

2. **Configure Webhook:**
   - Webhook URL: `https://your-domain.com/webhook`
   - Event subscription: `meeting.rtms_started`
   - Enable signature validation

3. **Get Credentials:**
   - Copy Client ID → `ZM_RTMS_CLIENT`
   - Copy Client Secret → `ZM_RTMS_SECRET`

4. **Deploy & Validate:**
   - Deploy bot-rtms to EC2 with SSL
   - Zoom will send validation challenge to webhook URL
   - Bot responds with plainToken to complete validation

### SSL/Domain Setup

```bash
# Install nginx and certbot
sudo apt install nginx certbot python3-certbot-nginx

# Configure nginx reverse proxy
# /etc/nginx/sites-available/zoom-bot
server {
    server_name your-domain.com;

    location /webhook {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## Error Handling

### RTMS Connection Errors

```typescript
client.onLeave((reason) => {
  console.error(`Meeting ${meetingId} left: ${reason}`);

  if (reason === 'connection_error') {
    // Log error, cleanup, notify monitoring
    // DO NOT auto-reconnect (meeting might be ended)
  }

  this.handleMeetingEnd(meetingId);
});
```

### Storage Errors

```typescript
try {
  storage.saveSegment(meetingId, segment);
} catch (error) {
  console.error(`Storage error for ${meetingId}:`, error);
  // SQLite locking handled by better-sqlite3
  // Log error and continue (transcript might be partial)
}
```

### Bedrock API Errors

```typescript
async function generateSummaryWithRetry(meetingId: string): Promise<string> {
  const maxRetries = 3;
  let lastError;

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await generateSummary(meetingId);
    } catch (error) {
      lastError = error;
      await sleep(Math.pow(2, i) * 1000); // Exponential backoff
    }
  }

  console.error(`Summary generation failed after ${maxRetries} retries:`, lastError);
  return "Summary generation failed. Please review the transcript.";
}
```

## Cost Analysis

### Current System (GPU-based)

- EC2 g4dn.xlarge: ~$350/month
- EBS storage: ~$30/month
- Data transfer: ~$5/month
- **Total: ~$385/month**

### New System (RTMS-based)

- EC2 t3.small: ~$15/month
- EBS storage: ~$3/month (less storage needed)
- Data transfer: ~$1/month (less traffic)
- Zoom RTMS: $0 (included in Pro plan)
- **Total: ~$18/month**

**Savings: $367/month (95% reduction)**

## Migration Strategy

### Phase 1: Development (3-4 days)

1. **Project Setup** (4 hours)
   - Create `bot-rtms/` directory
   - Initialize TypeScript project
   - Setup Docker configuration

2. **Core Implementation** (2 days)
   - Implement webhook handler with signature validation
   - Implement RTMS Client Manager
   - Port storage layer from Python
   - Port WebSocket server from Python
   - Port summarizer from Python

3. **Testing** (1-2 days)
   - Unit tests for storage, summarizer
   - Integration tests with mock RTMS events
   - Local testing with Zoom dev account

### Phase 2: Deployment (1 day)

1. **Infrastructure Setup**
   - Setup domain DNS
   - Install nginx + certbot on EC2
   - Configure SSL certificate

2. **Docker Deployment**
   - Update docker-compose.yml
   - Remove Python bot service
   - Remove Speaches service
   - Deploy bot-rtms service

3. **Zoom Configuration**
   - Register Zoom Marketplace app
   - Configure webhook URL
   - Validate webhook endpoint

### Phase 3: Validation (1 day)

1. **End-to-End Testing**
   - Start test Zoom meeting
   - Verify bot joins via webhook
   - Check transcript appears in real-time
   - Verify dashboard updates
   - Test meeting end and summary generation

2. **Concurrent Meeting Test**
   - Start 2-3 meetings simultaneously
   - Verify all transcripts are captured
   - Check no memory leaks

### Rollback Plan

- Keep Python bot code in git (deprecated but available)
- Can redeploy old system if critical issues found
- API/Dashboard unchanged, so no risk there
- SQLite schema unchanged, data compatible

## Success Criteria

- ✅ Bot successfully joins Zoom meetings via webhook
- ✅ Real-time transcript appears in dashboard
- ✅ Meeting summaries generated correctly
- ✅ Multiple concurrent meetings work
- ✅ No Zoom detection issues
- ✅ System cost reduced to ~$18/month
- ✅ All existing API/Dashboard functionality preserved

## Risks & Mitigations

**Risk: RTMS SDK has bugs or limitations**
- Mitigation: SDK is production-ready, used by major companies
- Mitigation: Extensive testing in Phase 1

**Risk: Transcript quality lower than Whisper**
- Mitigation: Zoom's transcript is high-quality, speaker-attributed
- Mitigation: Can add audio stream fallback if needed in future

**Risk: Zoom Marketplace approval delays**
- Mitigation: Start app registration early in Phase 1
- Mitigation: Development can proceed with dev credentials

**Risk: Migration breaks existing functionality**
- Mitigation: API/Dashboard unchanged, minimal risk
- Mitigation: Rollback plan available

## Future Enhancements

Once RTMS migration is stable, we can add:

1. **Audio recording** - Use `onAudioData` to save audio files
2. **Video capture** - Use `onVideoData` for video recording
3. **Active speaker highlighting** - Use `onActiveSpeakerEvent`
4. **Live captions** - Inject captions back into Zoom via API
5. **Multi-language support** - Zoom transcripts support multiple languages

## Conclusion

Migrating to Zoom RTMS SDK solves the critical detection blocker while dramatically simplifying the system and reducing costs by 95%. The official SDK provides better reliability, maintainability, and feature completeness compared to web scraping. With careful migration planning and testing, this upgrade can be completed in approximately one week with minimal risk.

---

**Next Step:** Create detailed implementation plan using writing-plans skill.
