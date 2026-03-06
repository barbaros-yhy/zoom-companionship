# bot/tests/test_playwright_bot.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_bot_join_sets_is_joined_true():
    """After joining, bot.is_joined should be True."""
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot(display_name="Companion")

    mock_page = AsyncMock()
    mock_page.query_selector = AsyncMock(return_value=AsyncMock(
        fill=AsyncMock(), click=AsyncMock()
    ))

    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("bot.playwright_bot.async_playwright") as mock_pw_class:
        mock_pw_class.return_value.start = AsyncMock(return_value=mock_pw)

        with patch("bot.playwright_bot.asyncio.sleep", new_callable=AsyncMock):
            await bot.join("https://zoom.us/j/123456789")

    assert bot.is_joined is True
    assert bot._page is not None  # browser NOT closed after join


@pytest.mark.asyncio
async def test_get_active_speaker_returns_name():
    """get_active_speaker should return the text of the active speaker element."""
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot(display_name="Companion")
    bot._page = AsyncMock()

    mock_el = AsyncMock()
    mock_el.inner_text = AsyncMock(return_value="Barbaros Yahya")
    bot._page.query_selector = AsyncMock(return_value=mock_el)

    speaker = await bot.get_active_speaker()
    assert speaker == "Barbaros Yahya"


@pytest.mark.asyncio
async def test_get_active_speaker_returns_none_when_no_element():
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot(display_name="Companion")
    bot._page = AsyncMock()
    bot._page.query_selector = AsyncMock(return_value=None)

    speaker = await bot.get_active_speaker()
    assert speaker is None


@pytest.mark.asyncio
async def test_get_active_speaker_returns_none_without_page():
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot(display_name="Companion")
    speaker = await bot.get_active_speaker()
    assert speaker is None


def test_bot_initial_state():
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot(display_name="TestBot")
    assert bot.display_name == "TestBot"
    assert bot.is_joined is False
    assert bot._page is None


def test_validate_url_rejects_non_zoom():
    from bot.playwright_bot import ZoomBot
    import pytest as pt

    bot = ZoomBot()
    with pt.raises(ValueError):
        bot._validate_url("https://evil.com/j/123")


def test_validate_url_accepts_zoom():
    from bot.playwright_bot import ZoomBot

    bot = ZoomBot()
    bot._validate_url("https://zoom.us/j/123456789")  # should not raise
