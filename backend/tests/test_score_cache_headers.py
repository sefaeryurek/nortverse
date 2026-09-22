"""Recent score pages need shorter shared cache lifetimes."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.api.main import add_cache_headers


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/fixture", "/api/results"])
async def test_today_and_yesterday_use_short_score_cache(path):
    today = datetime.now(timezone(timedelta(hours=3))).date()

    async def call_next(_request):
        return Response(status_code=200)

    for offset, expected_max_age in ((0, "15"), (1, "15"), (2, "300" if path.endswith("fixture") else "120")):
        query = urlencode({"date": (today - timedelta(days=offset)).isoformat()}).encode()
        request = Request({"type": "http", "method": "GET", "path": path, "query_string": query,
                           "headers": []})
        response = await add_cache_headers(request, call_next)
        assert f"s-maxage={expected_max_age}" in response.headers["Cache-Control"]
