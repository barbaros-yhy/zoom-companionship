import rtms from '@zoom/rtms';
import { createHmac } from 'crypto';
import { Storage } from './storage.js';
import { TranscriptWSServer } from './websocket-server.js';
import { Summarizer } from './summarizer.js';
import { RTMSClientManager } from './rtms-client-manager.js';
import type { ZoomWebhookEvent } from './types.js';

// Load environment variables
const RTMS_CLIENT = process.env.ZM_RTMS_CLIENT;
const RTMS_SECRET = process.env.ZM_RTMS_SECRET;
const RTMS_PORT = parseInt(process.env.ZM_RTMS_PORT || '8080');
const WS_PORT = parseInt(process.env.BOT_WS_PORT || '8765');
const DB_PATH = process.env.DB_PATH || './data/meetings.db';
const TRANSCRIPT_DIR = process.env.TRANSCRIPT_DIR || './data/transcripts';
const AWS_REGION = process.env.AWS_REGION || 'eu-central-1';

if (!RTMS_CLIENT || !RTMS_SECRET) {
  console.error('ERROR: ZM_RTMS_CLIENT and ZM_RTMS_SECRET must be set');
  process.exit(1);
}

// Initialize services
const storage = new Storage(DB_PATH, TRANSCRIPT_DIR);
const wsServer = new TranscriptWSServer(WS_PORT);
const summarizer = new Summarizer(AWS_REGION);
const clientManager = new RTMSClientManager(storage, wsServer, summarizer);

// Start WebSocket server
await wsServer.start();
console.log(`WebSocket server started on port ${WS_PORT}`);

// Setup RTMS webhook handler
rtms.onWebhookEvent((webhookPayload: Record<string, any>, req: any, res: any) => {
  const { event, payload } = webhookPayload as ZoomWebhookEvent;
  console.log(`Received webhook event: ${event}`);

  // Handle Zoom webhook validation challenge
  if (req.headers['x-zoom-webhook-validator']) {
    const plainToken = req.headers['x-zoom-webhook-validator'] as string;
    const encryptedToken = createHmac('sha256', RTMS_SECRET!)
      .update(plainToken)
      .digest('hex');
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ plainToken, encryptedToken }));
    console.log('Webhook validation challenge completed');
    return;
  }

  // Handle RTMS started event
  if (event === 'meeting.rtms_started') {
    const meetingUuid = payload.meeting_uuid;
    console.log(`Meeting started: ${meetingUuid}`);

    // Create meeting in database
    const meetingId = storage.createMeeting(
      `Meeting ${meetingUuid}`,
      'zoom',
      `zoom://meeting/${meetingUuid}`
    );

    // Create RTMS client for this meeting
    clientManager.createClient(meetingId, payload);

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', meeting_id: meetingId }));
    return;
  }

  // Unknown event
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ status: 'ignored' }));
});

console.log(`RTMS webhook server listening on port ${RTMS_PORT}`);
console.log(`Active clients: ${clientManager.getActiveClientCount()}`);

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('\nShutting down gracefully...');
  await wsServer.stop();
  storage.close();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\nShutting down gracefully...');
  await wsServer.stop();
  storage.close();
  process.exit(0);
});
