// bot-rtms/src/rtms-client-manager.ts
import rtms from '@zoom/rtms';
import type { Storage } from './storage.js';
import type { TranscriptWSServer } from './websocket-server.js';
import type { Summarizer } from './summarizer.js';
import type { RTMSClientInstance, TranscriptMetadata } from './types.js';

/**
 * Factory function type for creating RTMS clients.
 * Allows dependency injection for testing.
 */
type ClientFactory = () => any;

/**
 * Manages multiple concurrent RTMS clients (one per meeting).
 *
 * Coordinates transcript callbacks with Storage/WebSocket/Summarizer.
 * Handles meeting lifecycle: join → transcribe → summarize → cleanup.
 */
export class RTMSClientManager {
  private clients: Map<string, RTMSClientInstance> = new Map();
  private clientFactory: ClientFactory;

  constructor(
    private storage: Storage,
    private wsServer: TranscriptWSServer,
    private summarizer: Summarizer,
    clientFactory?: ClientFactory
  ) {
    this.clientFactory = clientFactory || (() => new rtms.Client());
  }

  /**
   * Create and join an RTMS client for a meeting.
   * Sets up callbacks for transcript data, participants, and meeting end.
   *
   * @param meetingId Internal meeting ID (8-char UUID)
   * @param payload RTMS join payload from Zoom webhook
   */
  createClient(meetingId: string, payload: any): void {
    if (this.clients.has(meetingId)) {
      console.log(`[${meetingId}] Client already exists, skipping creation`);
      return;
    }

    const client = this.clientFactory();
    const participants = new Set<string>();
    const startTime = Date.now();

    // Handle join confirmation
    client.onJoinConfirm((reason: number) => {
      console.log(`[${meetingId}] Joined RTMS session with reason code: ${reason}`);
    });

    // Handle transcript data - CORE CALLBACK
    client.onTranscriptData((buffer: Buffer, _size: number, _timestamp: number, metadata: TranscriptMetadata) => {
      const text = buffer.toString('utf-8').trim();
      if (!text) return;

      const speaker = metadata.userName || 'Unknown';

      // Calculate elapsed timestamp in HH:MM:SS format
      const elapsedMs = Date.now() - startTime;
      const timestampStr = this.formatElapsedTime(elapsedMs);

      // Save to storage
      this.storage.appendSegment(meetingId, speaker, text, timestampStr);

      // Broadcast to WebSocket clients (match Python bot format)
      this.wsServer.broadcast({
        meeting_id: meetingId,
        speaker,
        text,
        timestamp: timestampStr,
      });

      // Track participant
      participants.add(speaker);
    });

    // Handle participant events
    client.onParticipantEvent((event: 'join' | 'leave', _timestamp: number, participantList: any[]) => {
      participantList.forEach((p) => {
        const userName = p.userName || `User_${p.userId}`;
        if (event === 'join') {
          participants.add(userName);
          console.log(`[${meetingId}] Participant joined: ${userName}`);
        } else if (event === 'leave') {
          console.log(`[${meetingId}] Participant left: ${userName}`);
        }
      });
    });

    // Handle meeting end
    client.onLeave(async (reason: number) => {
      console.log(`[${meetingId}] Meeting ended with reason code: ${reason}`);
      await this.handleMeetingEnd(meetingId, participants);
      this.removeClient(meetingId);
    });

    // Join the meeting
    client.join(payload);

    // Store client instance
    this.clients.set(meetingId, {
      client,
      startTime,
      participants,
    });

    console.log(`[${meetingId}] RTMS client created and joined`);
  }

  /**
   * Remove and cleanup RTMS client for a meeting.
   * Calls client.leave() to disconnect gracefully.
   *
   * @param meetingId Internal meeting ID
   */
  removeClient(meetingId: string): void {
    const instance = this.clients.get(meetingId);
    if (!instance) {
      return;
    }

    try {
      instance.client.leave();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[${meetingId}] Error leaving RTMS client: ${errorMessage}`);
    }

    this.clients.delete(meetingId);
    console.log(`[${meetingId}] RTMS client removed`);
  }

  /**
   * Check if a client exists for a meeting.
   *
   * @param meetingId Internal meeting ID
   * @returns true if client exists
   */
  hasClient(meetingId: string): boolean {
    return this.clients.has(meetingId);
  }

  /**
   * Get number of active RTMS clients.
   *
   * @returns Count of active clients
   */
  getActiveClientCount(): number {
    return this.clients.size;
  }

  /**
   * Handle meeting end: generate summary, save to storage, broadcast.
   * Does not throw on errors (logs instead).
   *
   * @param meetingId Internal meeting ID
   * @param participants Set of participant names
   */
  private async handleMeetingEnd(meetingId: string, participants: Set<string>): Promise<void> {
    try {
      // Get transcript segments
      const segments = this.storage.getSegments(meetingId);
      if (segments.length === 0) {
        console.log(`[${meetingId}] No segments to summarize`);
        // Still mark as completed even without segments
        this.storage.completeMeeting(meetingId, '', [], Array.from(participants));
        return;
      }

      // Format transcript for summarization: [timestamp] speaker: text
      const transcript = segments
        .map((s) => `[${s.timestamp}] ${s.speaker}: ${s.text}`)
        .join('\n');

      // Generate summary (may fail, don't crash)
      console.log(`[${meetingId}] Generating summary...`);
      const result = await this.summarizer.generate(transcript, Array.from(participants));

      // Save summary
      const summaryText = result.summary.join('\n');
      this.storage.completeMeeting(
        meetingId,
        summaryText,
        result.action_items,
        Array.from(participants)
      );

      console.log(`[${meetingId}] Summary generated and saved`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[${meetingId}] Error handling meeting end: ${errorMessage}`);

      // Still mark meeting as completed even if summary fails
      try {
        this.storage.completeMeeting(
          meetingId,
          'Summary generation failed',
          [],
          Array.from(participants)
        );
      } catch (storageError) {
        console.error(`[${meetingId}] Failed to mark meeting as completed:`, storageError);
      }
    }
  }

  /**
   * Format elapsed time in milliseconds as HH:MM:SS.
   *
   * @param elapsedMs Elapsed time in milliseconds
   * @returns Formatted timestamp string
   */
  private formatElapsedTime(elapsedMs: number): string {
    const totalSeconds = Math.floor(elapsedMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
}
