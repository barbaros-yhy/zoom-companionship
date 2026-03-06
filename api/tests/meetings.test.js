// api/tests/meetings.test.js
const path = require('path');
const os = require('os');

// Use a temp DB for tests
process.env.DB_PATH = path.join(os.tmpdir(), `test-meetings-${Date.now()}.db`);

const { handler } = require('../handlers/meetings');

describe('GET /meetings', () => {
  it('returns an empty array when no meetings exist', async () => {
    const event = { httpMethod: 'GET', path: '/meetings' };
    const result = await handler(event);
    expect(result.statusCode).toBe(200);
    expect(JSON.parse(result.body)).toEqual([]);
  });
});

describe('POST /meetings', () => {
  it('creates a meeting and returns meeting_id', async () => {
    const event = {
      httpMethod: 'POST',
      path: '/meetings',
      body: JSON.stringify({ meeting_url: 'https://zoom.us/j/123', title: 'Test Meeting' }),
    };
    const result = await handler(event);
    expect(result.statusCode).toBe(201);
    const body = JSON.parse(result.body);
    expect(body.meeting_id).toBeDefined();
    expect(body.meeting_id).toHaveLength(8);
  });

  it('returns 400 when meeting_url is missing', async () => {
    const event = {
      httpMethod: 'POST',
      path: '/meetings',
      body: JSON.stringify({ title: 'No URL' }),
    };
    const result = await handler(event);
    expect(result.statusCode).toBe(400);
  });
});

describe('GET /meetings/:id', () => {
  it('returns 404 for unknown id', async () => {
    const event = { httpMethod: 'GET', path: '/meetings/nonexistent' };
    const result = await handler(event);
    expect(result.statusCode).toBe(404);
  });

  it('returns the created meeting', async () => {
    // Create a meeting first
    const createResult = await handler({
      httpMethod: 'POST',
      path: '/meetings',
      body: JSON.stringify({ meeting_url: 'https://zoom.us/j/456', title: 'Get Test' }),
    });
    const { meeting_id } = JSON.parse(createResult.body);

    const getResult = await handler({ httpMethod: 'GET', path: `/meetings/${meeting_id}` });
    expect(getResult.statusCode).toBe(200);
    const meeting = JSON.parse(getResult.body);
    expect(meeting.id).toBe(meeting_id);
    expect(meeting.title).toBe('Get Test');
  });
});
