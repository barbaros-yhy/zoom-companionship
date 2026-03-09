// bot-rtms/src/storage.ts
import Database from 'better-sqlite3';
import * as fs from 'fs';
import * as path from 'path';
import { Meeting, Segment } from './types.js';
import { randomUUID } from 'crypto';

/**
 * Storage layer for meeting metadata and transcripts.
 * Matches Python bot/storage.py schema for API compatibility.
 */
export class Storage {
  private db: Database.Database;
  private transcriptDir: string;

  /**
   * Initialize storage with SQLite database and transcript directory.
   * Creates tables if they don't exist.
   */
  constructor(dbPath: string, transcriptDir: string) {
    this.transcriptDir = transcriptDir;

    // Create transcript directory if it doesn't exist
    fs.mkdirSync(transcriptDir, { recursive: true });

    // Initialize SQLite database
    this.db = new Database(dbPath);
    this.initDb();
  }

  /**
   * Create database tables matching Python storage.py schema.
   */
  private initDb(): void {
    // meetings table - MUST match Python schema exactly
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS meetings (
        id TEXT PRIMARY KEY,
        title TEXT,
        platform TEXT,
        meeting_url TEXT,
        date TEXT,
        status TEXT DEFAULT 'ongoing',
        summary TEXT,
        action_items TEXT DEFAULT '[]',
        participants TEXT DEFAULT '[]'
      )
    `);

    // segments table - MUST match Python schema exactly
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS segments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id TEXT,
        speaker TEXT,
        text TEXT,
        timestamp TEXT,
        created_at TEXT
      )
    `);
  }

  /**
   * Create a new meeting record.
   * Returns 8-character meeting ID (first 8 chars of UUID).
   */
  createMeeting(title: string, platform: string, meetingUrl: string): string {
    const meetingId = randomUUID().slice(0, 8);
    const date = new Date().toISOString();

    const stmt = this.db.prepare(`
      INSERT INTO meetings (id, title, platform, meeting_url, date)
      VALUES (?, ?, ?, ?, ?)
    `);

    stmt.run(meetingId, title, platform, meetingUrl, date);

    return meetingId;
  }

  /**
   * Retrieve meeting by ID.
   * Returns null if meeting doesn't exist.
   */
  getMeeting(meetingId: string): Meeting | null {
    const stmt = this.db.prepare('SELECT * FROM meetings WHERE id = ?');
    const row = stmt.get(meetingId) as Meeting | undefined;

    return row ?? null;
  }

  /**
   * List all meetings ordered by date DESC.
   */
  listMeetings(): Meeting[] {
    const stmt = this.db.prepare('SELECT * FROM meetings ORDER BY date DESC');
    return stmt.all() as Meeting[];
  }

  /**
   * Append transcript segment to database and markdown file.
   */
  appendSegment(
    meetingId: string,
    speaker: string,
    text: string,
    timestamp: string
  ): void {
    const createdAt = new Date().toISOString();

    // Insert into database
    const stmt = this.db.prepare(`
      INSERT INTO segments (meeting_id, speaker, text, timestamp, created_at)
      VALUES (?, ?, ?, ?, ?)
    `);

    stmt.run(meetingId, speaker, text, timestamp, createdAt);

    // Append to markdown transcript file
    const transcriptPath = path.join(
      this.transcriptDir,
      `${meetingId}_transcript.md`
    );

    const line = `[${timestamp}] **${speaker}:** ${text}\n\n`;
    fs.appendFileSync(transcriptPath, line, 'utf-8');
  }

  /**
   * Get all segments for a meeting ordered by ID.
   */
  getSegments(meetingId: string): Segment[] {
    const stmt = this.db.prepare(
      'SELECT * FROM segments WHERE meeting_id = ? ORDER BY id'
    );
    return stmt.all(meetingId) as Segment[];
  }

  /**
   * Mark meeting as completed with summary and action items.
   * Optionally update participants list.
   */
  completeMeeting(
    meetingId: string,
    summary: string,
    actionItems: string[],
    participants?: string[]
  ): void {
    if (participants !== undefined) {
      const stmt = this.db.prepare(`
        UPDATE meetings
        SET status = ?, summary = ?, action_items = ?, participants = ?
        WHERE id = ?
      `);

      stmt.run(
        'completed',
        summary,
        JSON.stringify(actionItems),
        JSON.stringify(participants),
        meetingId
      );
    } else {
      const stmt = this.db.prepare(`
        UPDATE meetings
        SET status = ?, summary = ?, action_items = ?
        WHERE id = ?
      `);

      stmt.run('completed', summary, JSON.stringify(actionItems), meetingId);
    }
  }

  /**
   * Close database connection.
   */
  close(): void {
    this.db.close();
  }
}
