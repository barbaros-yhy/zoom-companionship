// api/server.js
const http = require('http');
const { handler } = require('./handlers/meetings');

const PORT = process.env.PORT || 3001;

const server = http.createServer(async (req, res) => {
  let body = '';
  req.on('data', (chunk) => (body += chunk));
  req.on('end', async () => {
    const event = {
      httpMethod: req.method,
      path: req.url,
      body: body || null,
      headers: req.headers,
    };
    try {
      const result = await handler(event);
      res.writeHead(result.statusCode, result.headers || { 'Content-Type': 'application/json' });
      res.end(result.body);
    } catch (err) {
      res.writeHead(500);
      res.end(JSON.stringify({ error: 'Internal server error' }));
    }
  });
});

server.listen(PORT, () => {
  console.log(`API server running on http://localhost:${PORT}`);
});
