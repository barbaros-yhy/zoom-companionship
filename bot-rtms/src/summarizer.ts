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

    const response = await this.client.send(command);

    // Parse the response
    const responseBody = JSON.parse(await response.body.transformToString());
    const text = responseBody.content[0].text;

    // Extract JSON from response (Claude might wrap it in explanation text)
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}') + 1;
    const jsonStr = text.substring(start, end);

    return JSON.parse(jsonStr) as SummaryResult;
  }
}
