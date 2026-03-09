// bot-rtms/src/summarizer.ts
import {
  BedrockRuntimeClient,
  InvokeModelCommand,
} from '@aws-sdk/client-bedrock-runtime';

const SYSTEM_PROMPT = `You are a meeting assistant. Given a meeting transcript, extract:
1. A bullet-point summary (5-10 key points)
2. Action items with owner names

Return ONLY valid JSON in this exact format:
{
  "summary": ["point 1", "point 2"],
  "action_items": ["Owner: action description"]
}`;

export interface SummaryResult {
  summary: string[];
  action_items: string[];
}

/**
 * Generates meeting summaries and action items using Claude Haiku via AWS Bedrock.
 * Uses EC2 instance role for authentication (no credentials needed in constructor).
 */
export class Summarizer {
  private static readonly MODEL_ID = 'anthropic.claude-haiku-4-5-20251001-v1:0';
  private client: BedrockRuntimeClient;

  /**
   * Creates a new Summarizer instance.
   * @param region AWS region for Bedrock (default: us-east-1)
   * @param client Optional BedrockRuntimeClient for testing
   */
  constructor(region: string = 'us-east-1', client?: BedrockRuntimeClient) {
    // No credentials needed — uses EC2 instance role automatically
    this.client = client ?? new BedrockRuntimeClient({ region });
  }

  /**
   * Generate meeting summary and action items.
   * @param transcript Full meeting transcript text
   * @param participants List of participant names
   * @returns Summary result with bullet points and action items
   * @throws Error if AWS API call fails, response parsing fails, or JSON validation fails
   */
  async generate(transcript: string, participants: string[]): Promise<SummaryResult> {
    const participantsStr = participants.length > 0 ? participants.join(', ') : 'Unknown';
    const userMessage = `Participants: ${participantsStr}\n\nTranscript:\n${transcript}`;

    const command = new InvokeModelCommand({
      modelId: Summarizer.MODEL_ID,
      body: JSON.stringify({
        anthropic_version: 'bedrock-2023-05-31',
        max_tokens: 1024,
        system: SYSTEM_PROMPT,
        messages: [{ role: 'user', content: userMessage }],
      }),
    });

    // Issue #2: Wrap AWS API call in try/catch
    let response;
    try {
      response = await this.client.send(command);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`AWS Bedrock API call failed: ${errorMessage}`);
    }

    // Issue #3: Wrap response parsing in try/catch
    let responseBody;
    let text: string;
    try {
      responseBody = JSON.parse(await response.body.transformToString());
      text = responseBody.content[0].text;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to parse AWS Bedrock response body: ${errorMessage}`);
    }

    // Issue #1: Check bounds before substring (indexOf returns -1 if not found)
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}') + 1;

    if (start === -1 || end === 0) {
      throw new Error(`No JSON object found in response text: ${text.substring(0, 100)}...`);
    }

    const jsonStr = text.substring(start, end);

    // Issue #3: Wrap JSON parsing in try/catch
    let result: unknown;
    try {
      result = JSON.parse(jsonStr);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to parse extracted JSON string: ${errorMessage}. JSON string: ${jsonStr.substring(0, 100)}...`);
    }

    // Issue #4: Validate parsed JSON structure
    if (typeof result !== 'object' || result === null) {
      throw new Error(`Parsed result is not an object: ${typeof result}`);
    }

    const summary = (result as any).summary;
    const actionItems = (result as any).action_items;

    if (!Array.isArray(summary)) {
      throw new Error(`Missing or invalid 'summary' field: expected array, got ${typeof summary}`);
    }

    if (!Array.isArray(actionItems)) {
      throw new Error(`Missing or invalid 'action_items' field: expected array, got ${typeof actionItems}`);
    }

    return { summary, action_items: actionItems };
  }
}
