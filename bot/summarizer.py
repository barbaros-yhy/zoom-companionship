# bot/summarizer.py
import json
import anthropic

SYSTEM_PROMPT = """You are a meeting assistant. Given a meeting transcript, extract:
1. A bullet-point summary (5-10 key points)
2. Action items with owner names

Return ONLY valid JSON in this exact format:
{
  "summary": ["point 1", "point 2"],
  "action_items": ["Owner: action description"]
}"""


class Summarizer:
    """Generates meeting summaries and action items using Claude Haiku."""

    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, transcript: str, participants: list[str]) -> dict:
        """Generate summary and action items from a meeting transcript."""
        participants_str = ", ".join(participants) if participants else "Unknown"
        user_message = (
            f"Participants: {participants_str}\n\nTranscript:\n{transcript}"
        )

        response = self._client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
