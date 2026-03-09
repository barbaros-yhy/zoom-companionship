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
  private isStopping: boolean = false;

  constructor(port: number = 8765) {
    this.port = port;
  }

  /**
   * Start WebSocket server and listen for client connections.
   * Binds to 0.0.0.0 to accept connections from any network interface.
   *
   * @throws Error if server fails to start (e.g., port already in use)
   */
  async start(): Promise<void> {
    this.server = new WebSocketServer({
      port: this.port,
      host: '0.0.0.0'
    });

    // Handle server-level errors (port in use, permission denied, etc.)
    this.server.on('error', (error: Error) => {
      console.error(`WebSocket server error on port ${this.port}:`, error.message);
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

    // Wait for server to start listening, or reject on error
    return new Promise((resolve, reject) => {
      // Set up error handler before listening
      const errorHandler = (error: Error) => {
        this.server?.removeListener('listening', listeningHandler);
        reject(new Error(`Failed to start WebSocket server on port ${this.port}: ${error.message}`));
      };

      const listeningHandler = () => {
        this.server?.removeListener('error', errorHandler);
        resolve();
      };

      this.server!.once('error', errorHandler);
      this.server!.once('listening', listeningHandler);
    });
  }

  /**
   * Stop WebSocket server and close all client connections.
   * Safe to call multiple times - subsequent calls will no-op.
   */
  async stop(): Promise<void> {
    if (!this.server || this.isStopping) {
      return;
    }

    // Prevent concurrent stop() calls
    this.isStopping = true;

    // Close all client connections
    for (const client of this.clients) {
      client.close();
    }
    this.clients.clear();

    // Close server
    return new Promise((resolve) => {
      this.server!.close(() => {
        this.server = null;
        this.isStopping = false;
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
