// bot-rtms/src/__tests__/summarizer.test.ts
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { Summarizer, type SummaryResult } from '../summarizer.js';
import type { BedrockRuntimeClient } from '@aws-sdk/client-bedrock-runtime';

describe('Summarizer', () => {
  let summarizer: Summarizer;
  let mockClient: jest.Mocked<BedrockRuntimeClient>;

  beforeEach(() => {
    // Create mock client
    mockClient = {
      send: jest.fn(),
    } as any;

    summarizer = new Summarizer('us-east-1', mockClient);
  });

  describe('constructor', () => {
    it('should accept region parameter', () => {
      // Constructor accepts region as first parameter
      const sum = new Summarizer('eu-central-1');
      expect(sum).toBeInstanceOf(Summarizer);
    });

    it('should use default region when not specified', () => {
      const sum = new Summarizer();
      expect(sum).toBeInstanceOf(Summarizer);
    });
  });

  describe('generate', () => {
    it('should call Bedrock client with correct parameters', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify({
                summary: ['Key point 1', 'Key point 2'],
                action_items: ['Alice: Complete report', 'Bob: Review document'],
              }),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      const transcript = 'Alice: Let me discuss the project.\nBob: I agree with that approach.';
      const participants = ['Alice', 'Bob'];

      await summarizer.generate(transcript, participants);

      expect(mockClient.send).toHaveBeenCalledTimes(1);
      const command = mockClient.send.mock.calls[0][0] as any;
      expect(command.input.modelId).toBe('anthropic.claude-haiku-4-5-20251001-v1:0');

      const body = JSON.parse(command.input.body);
      expect(body.messages[0].content).toContain('Participants: Alice, Bob');
      expect(body.messages[0].content).toContain(transcript);
    });

    it('should return parsed summary and action items', async () => {
      const expectedResult: SummaryResult = {
        summary: ['Discussed Q1 goals', 'Reviewed budget allocation', 'Planned next sprint'],
        action_items: ['Alice: Prepare slides', 'Bob: Update roadmap'],
      };

      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify(expectedResult),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      const transcript = 'Alice: We need to focus on Q1 goals.\nBob: I will update the roadmap.';
      const participants = ['Alice', 'Bob'];

      const result = await summarizer.generate(transcript, participants);

      expect(result).toEqual(expectedResult);
      expect(result.summary).toHaveLength(3);
      expect(result.action_items).toHaveLength(2);
    });

    it('should handle response with JSON embedded in text', async () => {
      const expectedResult: SummaryResult = {
        summary: ['Point 1'],
        action_items: ['Action 1'],
      };

      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: `Here is the summary:\n${JSON.stringify(expectedResult)}\nEnd of response`,
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      const result = await summarizer.generate('transcript', ['Alice']);

      expect(result).toEqual(expectedResult);
    });

    it('should handle empty participants list', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify({
                summary: ['Point 1'],
                action_items: [],
              }),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      const result = await summarizer.generate('transcript', []);

      expect(result).toBeDefined();
      expect(result.summary).toBeDefined();
      expect(result.action_items).toBeDefined();

      // Verify "Unknown" is used for empty participants
      const command = mockClient.send.mock.calls[0][0] as any;
      const body = JSON.parse(command.input.body);
      expect(body.messages[0].content).toContain('Participants: Unknown');
    });

    it('should format multiple participants correctly', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify({
                summary: ['Point 1'],
                action_items: [],
              }),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      const transcript = 'Meeting transcript';
      const participants = ['Alice', 'Bob', 'Charlie'];

      await summarizer.generate(transcript, participants);

      const command = mockClient.send.mock.calls[0][0] as any;
      const body = JSON.parse(command.input.body);

      expect(body.messages[0].content).toContain('Participants: Alice, Bob, Charlie');
      expect(body.messages[0].content).toContain('Transcript:\nMeeting transcript');
    });
  });

  describe('error handling', () => {
    it('should throw descriptive error when AWS API call fails', async () => {
      const awsError = new Error('ThrottlingException: Rate exceeded');
      (mockClient.send as any).mockRejectedValue(awsError);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow('AWS Bedrock API call failed: ThrottlingException: Rate exceeded');
    });

    it('should throw descriptive error when response body parsing fails', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve('invalid json'),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow('Failed to parse AWS Bedrock response body');
    });

    it('should throw descriptive error when response has no JSON object', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: 'No JSON object here, just plain text',
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow('No JSON object found in response text');
    });

    it('should throw descriptive error when extracted JSON is malformed', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: 'Here is the result: {summary: [invalid json}',
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow('Failed to parse extracted JSON string');
    });

    it('should throw descriptive error when summary field is missing', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify({
                action_items: ['Action 1'],
              }),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow("Missing or invalid 'summary' field: expected array, got undefined");
    });

    it('should throw descriptive error when action_items field is missing', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify({
                summary: ['Point 1'],
              }),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow("Missing or invalid 'action_items' field: expected array, got undefined");
    });

    it('should throw descriptive error when summary is not an array', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify({
                summary: 'Not an array',
                action_items: [],
              }),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow("Missing or invalid 'summary' field: expected array, got string");
    });

    it('should throw descriptive error when action_items is not an array', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: JSON.stringify({
                summary: ['Point 1'],
                action_items: 'Not an array',
              }),
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow("Missing or invalid 'action_items' field: expected array, got string");
    });

    it('should throw descriptive error when parsed result is not an object', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: '{"value": "just a string"}',
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      // This will pass JSON extraction but fail because "value" is a string, not an array
      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow("Missing or invalid 'summary' field");
    });

    it('should throw descriptive error when JSON parsing returns a number', async () => {
      const mockResponse = {
        body: {
          transformToString: () => Promise.resolve(JSON.stringify({
            content: [{
              text: 'Result: {42}',
            }],
          })),
        },
      };

      // @ts-expect-error - Mock response type
      mockClient.send.mockResolvedValue(mockResponse as any);

      // This will fail at JSON.parse stage because {42} is invalid JSON
      await expect(summarizer.generate('transcript', ['Alice']))
        .rejects
        .toThrow('Failed to parse extracted JSON string');
    });
  });
});
