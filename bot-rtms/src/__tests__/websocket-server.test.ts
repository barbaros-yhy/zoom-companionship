// bot-rtms/src/__tests__/websocket-server.test.ts
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { TranscriptWSServer } from '../websocket-server.js';
import WebSocket from 'ws';
import type { WSMessage } from '../types.js';

describe('TranscriptWSServer', () => {
  let server: TranscriptWSServer;
  const TEST_PORT = 8766; // Use different port to avoid conflicts

  beforeEach(() => {
    server = new TranscriptWSServer(TEST_PORT);
  });

  afterEach(async () => {
    await server.stop();
  });

  describe('start and stop', () => {
    it('should start server and accept client connections', async () => {
      await server.start();

      // Connect a client
      const client = new WebSocket(`ws://localhost:${TEST_PORT}`);

      // Wait for connection to open
      await new Promise<void>((resolve, reject) => {
        client.on('open', () => resolve());
        client.on('error', reject);
      });

      expect(client.readyState).toBe(WebSocket.OPEN);
      client.close();
    });

    it('should stop server and close all connections', async () => {
      await server.start();

      // Connect a client
      const client = new WebSocket(`ws://localhost:${TEST_PORT}`);

      // Wait for connection
      await new Promise<void>((resolve, reject) => {
        client.on('open', () => resolve());
        client.on('error', reject);
      });

      // Stop server
      await server.stop();

      // Wait for client to close
      await new Promise<void>((resolve) => {
        client.on('close', () => resolve());
      });

      expect(client.readyState).toBe(WebSocket.CLOSED);
    });
  });

  describe('broadcast', () => {
    it('should broadcast message to single client', async () => {
      await server.start();

      const client = new WebSocket(`ws://localhost:${TEST_PORT}`);

      // Wait for connection
      await new Promise<void>((resolve, reject) => {
        client.on('open', () => resolve());
        client.on('error', reject);
      });

      const testMessage: WSMessage = {
        meeting_id: 'test123',
        speaker: 'Alice',
        text: 'Hello world',
        timestamp: '00:00:05',
      };

      // Set up message listener
      const messagePromise = new Promise<WSMessage>((resolve) => {
        client.on('message', (data) => {
          resolve(JSON.parse(data.toString()));
        });
      });

      // Broadcast message
      server.broadcast(testMessage);

      // Verify client received message
      const received = await messagePromise;
      expect(received).toEqual(testMessage);

      client.close();
    });

    it('should broadcast message to multiple clients', async () => {
      await server.start();

      // Connect multiple clients
      const client1 = new WebSocket(`ws://localhost:${TEST_PORT}`);
      const client2 = new WebSocket(`ws://localhost:${TEST_PORT}`);
      const client3 = new WebSocket(`ws://localhost:${TEST_PORT}`);

      // Wait for all connections
      await Promise.all([
        new Promise<void>((resolve, reject) => {
          client1.on('open', () => resolve());
          client1.on('error', reject);
        }),
        new Promise<void>((resolve, reject) => {
          client2.on('open', () => resolve());
          client2.on('error', reject);
        }),
        new Promise<void>((resolve, reject) => {
          client3.on('open', () => resolve());
          client3.on('error', reject);
        }),
      ]);

      const testMessage: WSMessage = {
        meeting_id: 'test456',
        speaker: 'Bob',
        text: 'Broadcast test',
        timestamp: '00:01:30',
      };

      // Set up message listeners for all clients
      const messagePromises = [
        new Promise<WSMessage>((resolve) => {
          client1.on('message', (data) => resolve(JSON.parse(data.toString())));
        }),
        new Promise<WSMessage>((resolve) => {
          client2.on('message', (data) => resolve(JSON.parse(data.toString())));
        }),
        new Promise<WSMessage>((resolve) => {
          client3.on('message', (data) => resolve(JSON.parse(data.toString())));
        }),
      ];

      // Broadcast message
      server.broadcast(testMessage);

      // Verify all clients received message
      const received = await Promise.all(messagePromises);
      expect(received[0]).toEqual(testMessage);
      expect(received[1]).toEqual(testMessage);
      expect(received[2]).toEqual(testMessage);

      client1.close();
      client2.close();
      client3.close();
    });

    it('should handle broadcast when no clients are connected', async () => {
      await server.start();

      const testMessage: WSMessage = {
        meeting_id: 'test789',
        speaker: 'Charlie',
        text: 'No clients',
        timestamp: '00:02:15',
      };

      // Should not throw
      expect(() => server.broadcast(testMessage)).not.toThrow();
    });

    it('should remove client from tracking after disconnect', async () => {
      await server.start();

      const client = new WebSocket(`ws://localhost:${TEST_PORT}`);

      // Wait for connection
      await new Promise<void>((resolve, reject) => {
        client.on('open', () => resolve());
        client.on('error', reject);
      });

      // Close client
      client.close();

      // Wait for close
      await new Promise<void>((resolve) => {
        client.on('close', () => resolve());
      });

      const testMessage: WSMessage = {
        meeting_id: 'test999',
        speaker: 'Dave',
        text: 'After disconnect',
        timestamp: '00:03:00',
      };

      // Should not throw (client has been removed)
      expect(() => server.broadcast(testMessage)).not.toThrow();
    });
  });
});
