// api/db.js
const Database = require('better-sqlite3');
const path = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '../data/meetings.db');

let _db;

function getDb() {
  if (!_db) {
    _db = new Database(DB_PATH);
    _db.exec(`
      CREATE TABLE IF NOT EXISTS meetings (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        platform TEXT NOT NULL DEFAULT 'zoom',
        meeting_url TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ongoing',
        summary TEXT,
        action_items TEXT NOT NULL DEFAULT '[]',
        participants TEXT NOT NULL DEFAULT '[]'
      )
    `);
  }
  return _db;
}

module.exports = { getDb };
