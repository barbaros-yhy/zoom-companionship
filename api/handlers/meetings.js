// api/handlers/meetings.js
const { getDb } = require('../db');
const { v4: uuidv4 } = require('uuid');

exports.handler = async (event) => {
  const db = getDb();
  const method = event.httpMethod || event.method || 'GET';
  const path = event.path || '/meetings';

  // GET /meetings
  if (method === 'GET' && (path === '/meetings' || path === '/meetings/')) {
    const meetings = db.prepare('SELECT * FROM meetings ORDER BY date DESC').all();
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(meetings),
    };
  }

  // GET /meetings/:id/segments
  if (method === 'GET' && path.match(/^\/meetings\/[^/]+\/segments$/)) {
    const id = path.split('/')[2];
    // segments are stored in SQLite by the Python bot
    // This endpoint returns them for the dashboard
    try {
      const segments = db.prepare(
        'SELECT speaker, text, timestamp FROM segments WHERE meeting_id = ? ORDER BY id'
      ).all(id);
      return {
        statusCode: 200,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(segments),
      };
    } catch {
      // segments table may not exist if bot hasn't written yet
      return { statusCode: 200, body: JSON.stringify([]) };
    }
  }

  // GET /meetings/:id
  if (method === 'GET' && path.startsWith('/meetings/')) {
    const id = path.split('/')[2];
    const meeting = db.prepare('SELECT * FROM meetings WHERE id = ?').get(id);
    if (!meeting) {
      return { statusCode: 404, body: JSON.stringify({ error: 'Not found' }) };
    }
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(meeting),
    };
  }

  // POST /meetings
  if (method === 'POST' && (path === '/meetings' || path === '/meetings/')) {
    const body = typeof event.body === 'string' ? JSON.parse(event.body) : (event.body || {});
    const { meeting_url, title = 'Meeting', platform = 'zoom' } = body;

    if (!meeting_url) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'meeting_url is required' }),
      };
    }

    const id = uuidv4().slice(0, 8);
    db.prepare(
      'INSERT INTO meetings (id, title, platform, meeting_url, date) VALUES (?, ?, ?, ?, ?)'
    ).run(id, title, platform, meeting_url, new Date().toISOString());

    return {
      statusCode: 201,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meeting_id: id }),
    };
  }

  return {
    statusCode: 405,
    body: JSON.stringify({ error: 'Method not allowed' }),
  };
};
