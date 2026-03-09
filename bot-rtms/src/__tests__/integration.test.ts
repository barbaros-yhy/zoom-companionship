import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import { Storage } from '../storage.js';
import { TranscriptWSServer } from '../websocket-server.js';
import { Summarizer } from '../summarizer.js';
import WebSocket from 'ws';
import { rmSync, existsSync } from 'fs';

describe('Integration Test', () => {
  let storage: Storage;
  let wsServer: TranscriptWSServer;
  let summarizer: Summarizer;
  const TEST_TRANSCRIPT_DIR = './test-transcripts-integration';

  beforeAll(async () => {
    storage = new Storage(':memory:', TEST_TRANSCRIPT_DIR);
    wsServer = new TranscriptWSServer(9877);
    summarizer = new Summarizer('us-east-1');

    await wsServer.start();
  });

  afterAll(async () => {
    await wsServer.stop();
    storage.close();
    if (existsSync(TEST_TRANSCRIPT_DIR)) {
      rmSync(TEST_TRANSCRIPT_DIR, { recursive: true });
    }
  });

  it('should create meeting, receive transcripts, and complete with summary', async () => {
    // Create meeting
    const meetingId = storage.createMeeting('Integration Test', 'zoom', 'zoom://meeting/test-uuid');
    expect(meetingId).toBeTruthy();

    // Add segments
    storage.appendSegment(meetingId, 'Alice', 'We need to ship feature X', '10:00:00');
    storage.appendSegment(meetingId, 'Bob', 'I will handle the backend', '10:01:00');
    storage.appendSegment(meetingId, 'Alice', 'Great, I will do frontend', '10:02:00');

    // Verify segments saved
    const segments = storage.getSegments(meetingId);
    expect(segments).toHaveLength(3);
    expect(segments[0].speaker).toBe('Alice');
    expect(segments[1].speaker).toBe('Bob');

    // Complete meeting (skip summary to avoid AWS call)
    storage.completeMeeting(
      meetingId,
      'Test summary',
      ['Bob: backend', 'Alice: frontend'],
      ['Alice', 'Bob']
    );

    const meeting = storage.getMeeting(meetingId);
    expect(meeting?.status).toBe('completed');
    expect(meeting?.summary).toBe('Test summary');
  });

  it('should broadcast messages to WebSocket clients', (done) => {
    const client = new WebSocket('ws://localhost:9877');

    client.on('open', () => {
      wsServer.broadcast({
        meeting_id: 'test123',
        speaker: 'John',
        text: 'Hello',
        timestamp: '10:00:00',
      });
    });

    client.on('message', (data) => {
      const message = JSON.parse(data.toString());
      expect(message.speaker).toBe('John');
      expect(message.meeting_id).toBe('test123');
      client.close();
      done();
    });
  });

  it('should list all meetings from storage', () => {
    // Create a couple of meetings
    const id1 = storage.createMeeting('Meeting A', 'zoom', 'url1');
    const id2 = storage.createMeeting('Meeting B', 'zoom', 'url2');

    const meetings = storage.listMeetings();
    expect(meetings.length).toBeGreaterThanOrEqual(2);

    const foundId1 = meetings.find(m => m.id === id1);
    const foundId2 = meetings.find(m => m.id === id2);
    expect(foundId1).toBeDefined();
    expect(foundId2).toBeDefined();
  });

  it('should instantiate Summarizer without errors', () => {
    expect(summarizer).toBeDefined();
  });
});
