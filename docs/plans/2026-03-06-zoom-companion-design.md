# Zoom Companion Bot — Design Document

**Date:** 2026-03-06
**Status:** Approved

---

## Overview

A self-hosted meeting companion bot that joins Zoom (and later Google Meet, Teams) meetings as a visible participant, transcribes conversations in real-time with speaker identification, and generates post-meeting summaries with action items. All data stays on-premise — no third-party services process audio or transcripts.

---

## Requirements

- Bot joins Zoom meetings via a meeting link (server-side, headless)
- Real-time transcription with ~2-5 second latency
- Speaker identification (who said what)
- Turkish + English support with auto-detect
- Live transcript visible on web dashboard during meeting
- Post-meeting summary + action items (AI-generated)
- Transcripts togglable in meeting chat (visible to all or private)
- All data stays self-hosted on AWS (data security)

---

## Architecture

```
+------------------------------------------+
|         Web Dashboard (Next.js)          |
|  Live transcript · History · Summaries   |
+--------------------+---------------------+
                     | WebSocket
+--------------------+---------------------+
|         Backend API (AWS Lambda)         |
|   Bot orchestration · Auth · Routing     |
+--------------------+---------------------+
                     |
+--------------------+---------------------+
|      Bot Engine (EC2 g4dn.xlarge spot)   |
|                                          |
|  Playwright + Chromium                   |
|  +-- Zoom web client (Phase 1)           |
|  +-- Google Meet (Phase 2)               |
|  +-- Microsoft Teams (Phase 2)           |
|                                          |
|  PulseAudio (virtual audio device)       |
|  +-- Mixed audio capture                 |
|                                          |
|  Speaches (Docker, self-hosted)          |
|  +-- faster-whisper large-v3-turbo       |
|  +-- Real-time STT, TR+EN auto-detect    |
|  +-- ~2-5 second latency                 |
|                                          |
|  Caption scraper                         |
|  +-- Active speaker detection            |
|  +-- Name extraction from Zoom UI        |
+--------------------+---------------------+
                     |
+--------------------+---------------------+
|  Storage                                 |
|  S3     --> transcripts (.md files)      |
|  SQLite --> meeting metadata             |
+------------------------------------------+
```

---

## Tech Stack

| Layer            | Technology                              |
|------------------|-----------------------------------------|
| Bot Engine       | Python, Playwright, Chromium, PulseAudio|
| Transcription    | Speaches + faster-whisper large-v3-turbo|
| API              | Node.js, AWS Lambda                     |
| Dashboard        | Next.js                                 |
| AI Summary       | Claude API (Haiku)                      |
| Storage          | AWS S3 + SQLite                         |
| Infrastructure   | AWS EC2 g4dn.xlarge (spot instance)     |

---

## Detailed Flow

### 1. Meeting Join
```
User enters meeting link on dashboard
  -> Lambda triggers EC2 spot instance (if not running)
  -> Playwright launches headless Chromium
  -> Bot joins Zoom web client
     - Display name: "Companion" (configurable)
     - Avatar: custom logo via virtual camera
     - Chat message: "Transcription started"
```

### 2. Real-Time Transcription (during meeting)
```
PulseAudio captures meeting audio (mixed track)
  -> Audio streamed to Speaches via WebSocket
  -> Speaches (faster-whisper large-v3-turbo)
     - Auto-detects TR/EN language per chunk
     - Returns transcript text + timestamps
  -> Caption scraper reads Zoom active speaker
     - Maps current speaker name to transcript chunk
  -> {speaker: "Barbaros", text: "...", timestamp: "00:03:21"}
  -> WebSocket push to dashboard (live display)
  -> Appended to S3 transcript file (rolling .md)
```

### 3. Speaker Identification
```
Zoom web UI shows active speaker name
  -> Playwright scrapes speaker name in real-time
  -> Mapped to current transcript chunk
  -> ~2-5 second lag acceptable
  -> If two speakers overlap: last active speaker assigned
```

### 4. Meeting End
```
Meeting ends or bot is manually removed
  -> Final transcript flushed to S3 (.md file)
  -> Claude Haiku API called with full transcript
     - Generates: 5-10 bullet summary
     - Generates: action items with owner names
  -> Results saved to SQLite:
     {meeting_id, date, duration, participants[], s3_path, summary, action_items}
  -> Dashboard "Summary" page becomes available
```

### 5. Dashboard Routes
```
/meetings              -> List of all past meetings
/meetings/:id          -> Live transcript (if ongoing)
                          Full transcript + summary (if ended)
/meetings/:id/edit     -> Edit speaker names
/meetings/new          -> Paste meeting link to start bot
```

---

## Storage Design

### S3 — Transcript Files
```
s3://zoom-companion/
  transcripts/
    {meeting_id}/
      transcript.md     <- rolling append during meeting
      summary.md        <- generated post-meeting
```

Transcript format:
```markdown
## Meeting: Weekly Sync
**Date:** 2026-03-06  **Duration:** 47 min

---

[00:00:12] **Barbaros:** Merhaba, toplantiya baslayalim...
[00:00:18] **Ahmet:** Evet, hazir.
[00:00:24] **Barbaros:** Gecen haftaki action itemlara bakalim...
```

### SQLite — Metadata
```sql
meetings (
  id, title, platform, date, duration_sec,
  participants TEXT,   -- JSON array of names
  s3_transcript_path,
  s3_summary_path,
  status              -- ongoing | completed
)
```

---

## Cost Estimate

| Component                     | Cost         |
|-------------------------------|--------------|
| EC2 g4dn.xlarge (spot, ~$0.16/hr) | per meeting |
| AWS Lambda (API)              | ~$0/month    |
| S3 (transcript storage)       | ~$0.50/month |
| Claude Haiku (summaries)      | ~$0.02/meeting |

| Usage Scenario                | Monthly Cost |
|-------------------------------|--------------|
| 20 meetings x 1 hour          | ~$4          |
| 4 hours/day x 22 working days | ~$16         |

---

## Phased Rollout

### Phase 1 (MVP)
- Zoom only
- Playwright bot join
- Real-time transcription (TR + EN)
- Speaker identification via caption scraping
- Live dashboard
- Post-meeting summary + action items

### Phase 2
- Google Meet support (Playwright)
- Microsoft Teams support (Playwright)
- Meeting chat toggle (transcript visible to all participants)
- Speaker name editing on dashboard

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Bot joining mechanism | Playwright (all platforms) | Industry standard (used by Recall.ai et al.), single codebase for Zoom/Meet/Teams |
| Transcription engine | Speaches + whisper-large-v3-turbo | Self-hosted, 4.5x faster than large-v3, Turkish support, OpenAI API compatible |
| Speaker ID | Zoom caption scraping | RTMS would require Zoom app approval + OAuth complexity; caption scraping proven in production |
| Latency tolerance | 2-5 seconds | Acceptable for live transcript use case |
| Storage | S3 + SQLite | No managed DB needed, transcripts as readable .md files |
| Compute | EC2 spot instance | 60-70% cheaper than on-demand, auto-restart on preemption |
| Data residency | Fully self-hosted AWS | No third-party services (Recall.ai etc.) process audio |
