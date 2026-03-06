# bot/summarizer.py
import asyncio
import json
import boto3

SYSTEM_PROMPT = """You are a meeting assistant. Given a meeting transcript, extract:
1. A bullet-point summary (5-10 key points)
2. Action items with owner names

Return ONLY valid JSON in this exact format:
{
  "summary": ["point 1", "point 2"],
  "action_items": ["Owner: action description"]
}"""


class Summarizer:
    """Generates meeting summaries and action items using Claude Haiku via AWS Bedrock."""

    MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"

    def __init__(self, region: str = "us-east-1"):
        # No credentials needed — uses EC2 instance role automatically
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def generate(self, transcript: str, participants: list[str]) -> dict:
        """Generate summary synchronously (call via asyncio.to_thread in async context)."""
        participants_str = ", ".join(participants) if participants else "Unknown"
        user_message = f"Participants: {participants_str}\n\nTranscript:\n{transcript}"

        response = self._client.invoke_model(
            modelId=self.MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_message}],
            }),
        )

        result = json.loads(response["body"].read())
        text = result["content"][0]["text"]
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])

    async def generate_async(self, transcript: str, participants: list[str]) -> dict:
        """Async wrapper that runs generate() in a thread pool to avoid blocking the event loop."""
        return await asyncio.to_thread(self.generate, transcript, participants)
