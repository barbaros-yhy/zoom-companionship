// bot-rtms/src/types.ts

/**
 * Meeting record stored in SQLite database.
 * Matches the Python storage.py schema for API/dashboard compatibility.
 */
export interface Meeting {
  /** Unique meeting identifier (8-char UUID) */
  readonly id: string;
  /** Meeting title */
  title: string;
  /** Platform identifier (e.g., "zoom") */
  platform: string;
  /** Original meeting URL */
  meeting_url: string;
  /** Meeting start date/time (ISO 8601 string) */
  date: string;
  /** Meeting status */
  status: 'ongoing' | 'completed';
  /** AI-generated summary (optional, set after meeting ends) */
  summary?: string;
  /** JSON string array of action items (default: "[]") */
  action_items: string;
  /** JSON string array of participant names (default: "[]") */
  participants: string;
}

/**
 * Transcript segment from a meeting.
 * Stored in SQLite segments table and broadcast via WebSocket.
 */
export interface Segment {
  /** Auto-increment ID (optional for new segments) */
  id?: number;
  /** Associated meeting ID */
  meeting_id: string;
  /** Speaker display name */
  speaker: string;
  /** Transcript text */
  text: string;
  /** Formatted timestamp (e.g., "00:15:32") */
  timestamp: string;
  /** Segment creation time (ISO 8601 string, optional for new segments) */
  created_at?: string;
}

/**
 * Metadata from RTMS SDK onTranscriptData callback.
 * Provides speaker identification for each transcript segment.
 */
export interface TranscriptMetadata {
  /** Speaker's display name in Zoom */
  userName: string;
  /** Unique user ID from Zoom */
  userId: number;
}

/**
 * Participant information from RTMS SDK onParticipantEvent.
 * Tracks who joins/leaves the meeting.
 */
export interface Participant {
  /** Participant's display name */
  userName: string;
  /** Unique user ID from Zoom */
  userId: number;
}

/**
 * Summary result from AWS Bedrock summarizer.
 * Generated at meeting end using Claude Haiku.
 */
export interface SummaryResult {
  /** Array of summary bullet points (5-10 key points) */
  summary: string[];
  /** Array of action items with owner names */
  action_items: string[];
}

/**
 * WebSocket message format for real-time transcript streaming.
 * Must match dashboard/components/TranscriptView.tsx expectations.
 *
 * The dashboard expects segments to be sent directly with the format:
 * { meeting_id, speaker, text, timestamp }
 *
 * This matches the Python bot's ws_server.broadcast(segment) behavior.
 */
export type WSMessage = Segment;

/**
 * RTMS Client instance wrapper.
 * Manages a single meeting's RTMS connection and metadata.
 */
export interface RTMSClientInstance {
  /** RTMS Client instance (type: any to avoid SDK dependency in types) */
  client: any;
  /** Meeting start timestamp (milliseconds since epoch) */
  startTime: number;
  /** Set of participant user IDs who have joined */
  participants: Set<string>;
}

/**
 * Zoom webhook event payload structure.
 * Received when RTMS-enabled meetings start.
 */
export interface ZoomWebhookEvent {
  /** Event type (e.g., "meeting.rtms_started") */
  event: string;
  /** Event payload */
  payload: {
    /** Unique meeting UUID from Zoom */
    meeting_uuid: string;
    /** RTMS stream identifier */
    rtms_stream_id: string;
    /** Array of RTMS WebSocket server URLs */
    server_urls: string[];
    /** Webhook signature for verification (optional) */
    signature?: string;
  };
}
