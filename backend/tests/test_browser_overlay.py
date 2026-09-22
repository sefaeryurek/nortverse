from unittest.mock import AsyncMock, MagicMock

import pytest

from app.scraper.browser import close_ad_overlay


@pytest.mark.asyncio
async def test_absent_ad_overlay_does_not_wait_for_click_timeout():
    page = MagicMock()
    page.locator.return_value.count = AsyncMock(return_value=0)
    page.click = AsyncMock()

    assert await close_ad_overlay(page) is False
    page.click.assert_not_awaited()
