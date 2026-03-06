# bot/tests/test_summarizer.py
import pytest
import json
from unittest.mock import MagicMock, patch
from bot.summarizer import Summarizer

SAMPLE_TRANSCRIPT = """
[00:00:10] **Barbaros:** Bu sprint icin hedeflerimizi konusalim.
[00:00:20] **Ahmet:** Auth modulunu bitirmem gerekiyor.
[00:00:35] **Barbaros:** Tamam, Ahmet auth'u bitirecek. Ben dashboard'u aliyorum.
"""


def test_summarizer_returns_summary_and_action_items():
    summarizer = Summarizer(api_key="fake-key")

    mock_text = json.dumps({
        "summary": ["Sprint hedefleri konusuldu", "Is bolumu yapildi"],
        "action_items": ["Ahmet: auth modulunu bitir", "Barbaros: dashboard yap"],
    })

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=mock_text)]

    with patch.object(summarizer._client.messages, "create", return_value=mock_msg):
        result = summarizer.generate(
            transcript=SAMPLE_TRANSCRIPT,
            participants=["Barbaros", "Ahmet"],
        )

    assert "summary" in result
    assert "action_items" in result
    assert isinstance(result["summary"], list)
    assert isinstance(result["action_items"], list)
    assert len(result["summary"]) >= 1
    assert len(result["action_items"]) >= 1


def test_summarizer_uses_haiku_model():
    """Summarizer must use claude-haiku-4-5-20251001 model."""
    summarizer = Summarizer(api_key="fake-key")

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text='{"summary": ["x"], "action_items": ["y"]}')]

    with patch.object(summarizer._client.messages, "create", return_value=mock_msg) as mock_create:
        summarizer.generate(transcript="test", participants=[])
        call_kwargs = mock_create.call_args
        assert "claude-haiku-4-5" in call_kwargs.kwargs.get("model", "") or \
               "claude-haiku-4-5" in str(call_kwargs)


def test_summarizer_extracts_json_from_response():
    """Summarizer should handle response with text before/after JSON."""
    summarizer = Summarizer(api_key="fake-key")

    # Response with extra text around JSON (common LLM behavior)
    mock_text = 'Here is the summary:\n{"summary": ["Point 1"], "action_items": ["Do X"]}\nDone.'
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=mock_text)]

    with patch.object(summarizer._client.messages, "create", return_value=mock_msg):
        result = summarizer.generate(transcript="test", participants=[])

    assert result["summary"] == ["Point 1"]
    assert result["action_items"] == ["Do X"]
