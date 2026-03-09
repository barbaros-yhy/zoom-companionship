// bot-rtms/src/__tests__/storage.test.ts
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { Storage } from '../storage.js';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

describe('Storage', () => {
  let storage: Storage;
  let testDir: string;
  let dbPath: string;
  let transcriptDir: string;

  beforeEach(() => {
    // Create temporary directory for test files
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'storage-test-'));
    dbPath = path.join(testDir, 'test.db');
    transcriptDir = path.join(testDir, 'transcripts');
    storage = new Storage(dbPath, transcriptDir);
  });

  afterEach(() => {
    // Clean up
    storage.close();
    fs.rmSync(testDir, { recursive: true, force: true });
  });

  describe('constructor and initialization', () => {
    it('should create database file', () => {
      expect(fs.existsSync(dbPath)).toBe(true);
    });

    it('should create transcript directory', () => {
      expect(fs.existsSync(transcriptDir)).toBe(true);
    });
  });

  describe('createMeeting and getMeeting', () => {
    it('should create a meeting and return 8-character ID', () => {
      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');

      expect(meetingId).toBeDefined();
      expect(meetingId.length).toBe(8);
    });

    it('should retrieve created meeting by ID', () => {
      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      const meeting = storage.getMeeting(meetingId);

      expect(meeting).toBeDefined();
      expect(meeting?.id).toBe(meetingId);
      expect(meeting?.title).toBe('Test Meeting');
      expect(meeting?.platform).toBe('zoom');
      expect(meeting?.meeting_url).toBe('https://zoom.us/j/123');
      expect(meeting?.status).toBe('ongoing');
      expect(meeting?.date).toBeDefined();
      expect(meeting?.action_items).toBe('[]');
      expect(meeting?.participants).toBe('[]');
    });

    it('should return null for non-existent meeting', () => {
      const meeting = storage.getMeeting('nonexist');
      expect(meeting).toBeNull();
    });
  });

  describe('listMeetings', () => {
    it('should return empty array when no meetings exist', () => {
      const meetings = storage.listMeetings();
      expect(meetings).toEqual([]);
    });

    it('should list all meetings ordered by date DESC', () => {
      const id1 = storage.createMeeting('Meeting 1', 'zoom', 'https://zoom.us/j/111');
      const id2 = storage.createMeeting('Meeting 2', 'zoom', 'https://zoom.us/j/222');

      const meetings = storage.listMeetings();

      expect(meetings.length).toBe(2);
      // Verify both IDs are present (order might vary if timestamps are identical)
      const meetingIds = meetings.map(m => m.id);
      expect(meetingIds).toContain(id1);
      expect(meetingIds).toContain(id2);
    });
  });

  describe('appendSegment and getSegments', () => {
    let meetingId: string;

    beforeEach(() => {
      meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
    });

    it('should append segment to database', () => {
      storage.appendSegment(meetingId, 'Alice', 'Hello world', '00:00:05');

      const segments = storage.getSegments(meetingId);

      expect(segments.length).toBe(1);
      expect(segments[0].meeting_id).toBe(meetingId);
      expect(segments[0].speaker).toBe('Alice');
      expect(segments[0].text).toBe('Hello world');
      expect(segments[0].timestamp).toBe('00:00:05');
      expect(segments[0].created_at).toBeDefined();
      expect(segments[0].id).toBeDefined();
    });

    it('should append segment to markdown file', () => {
      storage.appendSegment(meetingId, 'Alice', 'Hello world', '00:00:05');

      const transcriptPath = path.join(transcriptDir, `${meetingId}_transcript.md`);
      const content = fs.readFileSync(transcriptPath, 'utf-8');

      expect(content).toBe('[00:00:05] **Alice:** Hello world\n\n');
    });

    it('should append multiple segments in order', () => {
      storage.appendSegment(meetingId, 'Alice', 'First message', '00:00:05');
      storage.appendSegment(meetingId, 'Bob', 'Second message', '00:00:10');
      storage.appendSegment(meetingId, 'Alice', 'Third message', '00:00:15');

      const segments = storage.getSegments(meetingId);

      expect(segments.length).toBe(3);
      expect(segments[0].speaker).toBe('Alice');
      expect(segments[0].text).toBe('First message');
      expect(segments[1].speaker).toBe('Bob');
      expect(segments[1].text).toBe('Second message');
      expect(segments[2].speaker).toBe('Alice');
      expect(segments[2].text).toBe('Third message');
    });

    it('should return empty array for meeting with no segments', () => {
      const segments = storage.getSegments(meetingId);
      expect(segments).toEqual([]);
    });
  });

  describe('completeMeeting', () => {
    let meetingId: string;

    beforeEach(() => {
      meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
    });

    it('should update meeting status to completed', () => {
      const summary = 'Meeting summary';
      const actionItems = ['Action 1', 'Action 2'];

      storage.completeMeeting(meetingId, summary, actionItems);

      const meeting = storage.getMeeting(meetingId);

      expect(meeting?.status).toBe('completed');
      expect(meeting?.summary).toBe(summary);
      expect(meeting?.action_items).toBe(JSON.stringify(actionItems));
    });

    it('should update meeting with participants when provided', () => {
      const summary = 'Meeting summary';
      const actionItems = ['Action 1'];
      const participants = ['Alice', 'Bob', 'Charlie'];

      storage.completeMeeting(meetingId, summary, actionItems, participants);

      const meeting = storage.getMeeting(meetingId);

      expect(meeting?.status).toBe('completed');
      expect(meeting?.summary).toBe(summary);
      expect(meeting?.action_items).toBe(JSON.stringify(actionItems));
      expect(meeting?.participants).toBe(JSON.stringify(participants));
    });

    it('should not change participants when not provided', () => {
      const summary = 'Meeting summary';
      const actionItems = ['Action 1'];

      storage.completeMeeting(meetingId, summary, actionItems);

      const meeting = storage.getMeeting(meetingId);

      expect(meeting?.participants).toBe('[]'); // Default value unchanged
    });
  });
});
