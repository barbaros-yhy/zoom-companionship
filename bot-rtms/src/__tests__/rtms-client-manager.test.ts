// bot-rtms/src/__tests__/rtms-client-manager.test.ts
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { RTMSClientManager } from '../rtms-client-manager.js';
import { Storage } from '../storage.js';
import { TranscriptWSServer } from '../websocket-server.js';
import { Summarizer } from '../summarizer.js';
import * as fs from 'fs';
import * as path from 'path';

// Mock RTMS client
let mockJoin: jest.Mock;
let mockLeave: jest.Mock;
let onJoinConfirmCallback: ((reason: number) => void) | null = null;
let onTranscriptDataCallback: ((data: Buffer, size: number, timestamp: number, metadata: any) => void) | null = null;
let onParticipantEventCallback: ((event: 'join' | 'leave', timestamp: number, participants: any[]) => void) | null = null;
let onLeaveCallback: ((reason: number) => void) | null = null;

function createMockClient() {
  return {
    join: mockJoin,
    leave: mockLeave,
    onJoinConfirm: jest.fn((callback: any) => {
      onJoinConfirmCallback = callback;
      return true;
    }),
    onTranscriptData: jest.fn((callback: any) => {
      onTranscriptDataCallback = callback;
      return true;
    }),
    onParticipantEvent: jest.fn((callback: any) => {
      onParticipantEventCallback = callback;
      return true;
    }),
    onLeave: jest.fn((callback: any) => {
      onLeaveCallback = callback;
      return true;
    }),
  };
}

describe('RTMSClientManager', () => {
  let manager: RTMSClientManager;
  let storage: Storage;
  let wsServer: TranscriptWSServer;
  let summarizer: Summarizer;
  const testDir = path.join('/tmp', `rtms-test-${Date.now()}`);

  beforeEach(() => {
    // Set fake credentials for RTMS SDK (required for tests)
    process.env.ZM_RTMS_CLIENT = 'test-client-id';
    process.env.ZM_RTMS_SECRET = 'test-client-secret';

    // Create test directory
    fs.mkdirSync(testDir, { recursive: true });

    // Initialize dependencies
    storage = new Storage(':memory:', testDir);
    wsServer = new TranscriptWSServer(19999); // Use high port to avoid conflicts
    summarizer = new Summarizer('us-east-1');

    // Reset mocks
    mockJoin = jest.fn();
    mockLeave = jest.fn();
    onJoinConfirmCallback = null;
    onTranscriptDataCallback = null;
    onParticipantEventCallback = null;
    onLeaveCallback = null;

    // Create manager with mock client factory
    manager = new RTMSClientManager(storage, wsServer, summarizer, createMockClient);
  });

  afterEach(() => {
    // Cleanup test directory
    if (fs.existsSync(testDir)) {
      fs.rmSync(testDir, { recursive: true, force: true });
    }
    storage.close();
  });

  describe('createClient', () => {
    it('should create a client for a meeting', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting123', payload);

      expect(manager.hasClient('meeting123')).toBe(true);
      expect(mockJoin).toHaveBeenCalledWith(payload);
      expect(manager.getActiveClientCount()).toBe(1);
    });

    it('should not create duplicate client for same meeting', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting123', payload);
      manager.createClient('meeting123', payload); // Try again

      expect(manager.getActiveClientCount()).toBe(1);
      expect(mockJoin).toHaveBeenCalledTimes(1);
    });

    it('should setup callbacks on client creation', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting123', payload);

      // Verify callbacks were registered
      expect(onJoinConfirmCallback).not.toBeNull();
      expect(onTranscriptDataCallback).not.toBeNull();
      expect(onParticipantEventCallback).not.toBeNull();
      expect(onLeaveCallback).not.toBeNull();
    });
  });

  describe('removeClient', () => {
    it('should remove a client', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting123', payload);
      expect(manager.hasClient('meeting123')).toBe(true);

      manager.removeClient('meeting123');
      expect(manager.hasClient('meeting123')).toBe(false);
      expect(mockLeave).toHaveBeenCalled();
      expect(manager.getActiveClientCount()).toBe(0);
    });

    it('should handle removing non-existent client gracefully', () => {
      expect(() => {
        manager.removeClient('nonexistent');
      }).not.toThrow();

      expect(mockLeave).not.toHaveBeenCalled();
    });

    it('should handle client.leave() errors gracefully', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting123', payload);

      // Mock leave to throw error
      mockLeave.mockImplementationOnce(() => {
        throw new Error('Network error');
      });

      expect(() => {
        manager.removeClient('meeting123');
      }).not.toThrow();

      // Client should still be removed from map
      expect(manager.hasClient('meeting123')).toBe(false);
    });
  });

  describe('onTranscriptData callback', () => {
    beforeEach(async () => {
      // Start WebSocket server for broadcast tests
      await wsServer.start();

      // Create meeting in storage
      storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
    });

    afterEach(async () => {
      await wsServer.stop();
    });

    it('should save transcript segment to storage', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      manager.createClient(meetingId, payload);

      // Simulate transcript data callback
      const transcriptData = Buffer.from('Hello world');
      const metadata = { userName: 'John Doe', userId: 12345 };

      onTranscriptDataCallback!(transcriptData, transcriptData.length, Date.now(), metadata);

      // Verify segment was saved
      const segments = storage.getSegments(meetingId);
      expect(segments.length).toBe(1);
      expect(segments[0].speaker).toBe('John Doe');
      expect(segments[0].text).toBe('Hello world');
      expect(segments[0].timestamp).toMatch(/^\d{2}:\d{2}:\d{2}$/); // HH:MM:SS format
    });

    it('should broadcast transcript segment to WebSocket', (done) => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      manager.createClient(meetingId, payload);

      // Mock WebSocket broadcast
      wsServer.broadcast = jest.fn((message: any) => {
        expect(message.meeting_id).toBe(meetingId);
        expect(message.speaker).toBe('John Doe');
        expect(message.text).toBe('Hello world');
        expect(message.timestamp).toMatch(/^\d{2}:\d{2}:\d{2}$/);
        done();
      }) as any;

      // Simulate transcript data callback
      const transcriptData = Buffer.from('Hello world');
      const metadata = { userName: 'John Doe', userId: 12345 };

      onTranscriptDataCallback!(transcriptData, transcriptData.length, Date.now(), metadata);
    });

    it('should skip empty transcript segments', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      manager.createClient(meetingId, payload);

      // Simulate empty transcript
      const transcriptData = Buffer.from('   '); // Only whitespace
      const metadata = { userName: 'John Doe', userId: 12345 };

      onTranscriptDataCallback!(transcriptData, transcriptData.length, Date.now(), metadata);

      // Verify no segment was saved
      const segments = storage.getSegments(meetingId);
      expect(segments.length).toBe(0);
    });

    it('should use "Unknown" speaker if metadata missing userName', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      manager.createClient(meetingId, payload);

      // Simulate transcript with missing userName
      const transcriptData = Buffer.from('Hello world');
      const metadata = { userName: '', userId: 12345 }; // Empty userName

      onTranscriptDataCallback!(transcriptData, transcriptData.length, Date.now(), metadata);

      // Verify segment has "Unknown" speaker
      const segments = storage.getSegments(meetingId);
      expect(segments.length).toBe(1);
      expect(segments[0].speaker).toBe('Unknown');
    });
  });

  describe('onParticipantEvent callback', () => {
    it('should track participants on join events', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting123', payload);

      // Simulate participant join
      const participants = [
        { userName: 'Alice', userId: 1 },
        { userName: 'Bob', userId: 2 },
      ];

      onParticipantEventCallback!('join', Date.now(), participants);

      // Participants are tracked internally (verified via meeting end)
      expect(manager.hasClient('meeting123')).toBe(true);
    });

    it('should log participant leave events', () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting123', payload);

      // Simulate participant leave
      const participants = [{ userName: 'Alice', userId: 1 }];

      onParticipantEventCallback!('leave', Date.now(), participants);

      // Should not crash
      expect(manager.hasClient('meeting123')).toBe(true);
    });
  });

  describe('onLeave callback', () => {
    it('should handle meeting end and cleanup client', async () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      manager.createClient(meetingId, payload);

      // Simulate transcript data callback (this tracks participants)
      const transcriptData = Buffer.from('Hello');
      const metadata = { userName: 'John', userId: 12345 };
      onTranscriptDataCallback!(transcriptData, transcriptData.length, Date.now(), metadata);

      // Mock summarizer to avoid AWS calls
      jest.spyOn(summarizer, 'generate').mockResolvedValue({
        summary: ['Meeting discussed project timeline'],
        action_items: ['John: Review design docs'],
      });

      // Simulate meeting end (reason code 0 = normal)
      await onLeaveCallback!(0);

      // Wait for async operations
      await new Promise(resolve => setTimeout(resolve, 100));

      // Verify client was removed
      expect(manager.hasClient(meetingId)).toBe(false);

      // Verify meeting was marked as completed
      const meeting = storage.getMeeting(meetingId);
      expect(meeting?.status).toBe('completed');
      expect(meeting?.summary).toBe('Meeting discussed project timeline');
      expect(meeting?.participants).toBe('["John"]');
    });

    it('should handle meeting end with no segments', async () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      manager.createClient(meetingId, payload);

      // Simulate meeting end with no transcript segments
      await onLeaveCallback!(0);

      // Wait for async operations
      await new Promise(resolve => setTimeout(resolve, 100));

      // Verify meeting was still marked as completed
      const meeting = storage.getMeeting(meetingId);
      expect(meeting?.status).toBe('completed');
    });

    it('should handle summarizer errors gracefully', async () => {
      const payload = {
        meeting_uuid: 'test-uuid',
        rtms_stream_id: 'stream-123',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const meetingId = storage.createMeeting('Test Meeting', 'zoom', 'https://zoom.us/j/123');
      manager.createClient(meetingId, payload);

      // Add a transcript segment
      storage.appendSegment(meetingId, 'John', 'Hello', '00:00:05');

      // Mock summarizer to throw error
      jest.spyOn(summarizer, 'generate').mockRejectedValue(new Error('AWS API error'));

      // Simulate meeting end (should not throw)
      await onLeaveCallback!(0);

      // Wait for async operations
      await new Promise(resolve => setTimeout(resolve, 100));

      // Verify meeting was still marked as completed
      const meeting = storage.getMeeting(meetingId);
      expect(meeting?.status).toBe('completed');
      expect(meeting?.summary).toBe('Summary generation failed');
    });
  });

  describe('multiple clients', () => {
    it('should manage multiple concurrent clients', () => {
      const payload1 = {
        meeting_uuid: 'uuid-1',
        rtms_stream_id: 'stream-1',
        server_urls: ['wss://rtms.zoom.us'],
      };

      const payload2 = {
        meeting_uuid: 'uuid-2',
        rtms_stream_id: 'stream-2',
        server_urls: ['wss://rtms.zoom.us'],
      };

      manager.createClient('meeting1', payload1);
      manager.createClient('meeting2', payload2);

      expect(manager.getActiveClientCount()).toBe(2);
      expect(manager.hasClient('meeting1')).toBe(true);
      expect(manager.hasClient('meeting2')).toBe(true);

      manager.removeClient('meeting1');

      expect(manager.getActiveClientCount()).toBe(1);
      expect(manager.hasClient('meeting1')).toBe(false);
      expect(manager.hasClient('meeting2')).toBe(true);
    });
  });
});
