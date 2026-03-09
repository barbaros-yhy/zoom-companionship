// bot-rtms/src/websocket-server.ts
import { WebSocketServer, WebSocket } from 'ws';
import type { WSMessage } from './types.js';

/**
 * WebSocket server that broadcasts transcript segments to dashboard clients.
 *
 * Manages client connections and broadcasts Segment objects in real-time.
 * Message format matches dashboard expectations (direct Segment objects).
 */
export class TranscriptWSServer {
  private port: number;
  private server: WebSocketServer | null = null;
  private clients: Set<WebSocket> = new Set();

  constructor(port: number = 8765) {
    this.port = port;
  }

  /**
   * Start WebSocket server and listen for client connections.
   * Binds to 0.0.0.0 to accept connections from any network interface.
   */
  async start(): Promise<void> {
    this.server = new WebSocketServer({
      port: this.port,
      host: '0.0.0.0'
    });

    this.server.on('connection', (ws: WebSocket) => {
      this.clients.add(ws);

      ws.on('close', () => {
        this.clients.delete(ws);
      });

      ws.on('error', () => {
        this.clients.delete(ws);
      });
    });

    // Wait for server to start listening
    return new Promise((resolve) => {
      this.server!.once('listening', () => resolve());
    });
  }

  /**
   * Stop WebSocket server and close all client connections.
   */
  async stop(): Promise<void> {
    if (!this.server) {
      return;
    }

    // Close all client connections
    for (const client of this.clients) {
      client.close();
    }
    this.clients.clear();

    // Close server
    return new Promise((resolve) => {
      this.server!.close(() => {
        this.server = null;
        resolve();
      });
    });
  }

  /**
   * Broadcast message to all connected clients.
   * Skips clients that are not in OPEN state.
   * Does not throw on client errors.
   *
   * @param message Segment object to broadcast
   */
  broadcast(message: WSMessage): void {
    if (this.clients.size === 0) {
      return;
    }

    const messageStr = JSON.stringify(message);

    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        try {
          client.send(messageStr);
        } catch (error) {
          // Ignore client send errors (client may have disconnected)
        }
      }
    }
  }
}
