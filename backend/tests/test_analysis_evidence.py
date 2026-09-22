from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.api import routes_admin


@pytest.mark.asyncio
async def test_evidence_reports_prematch_coverage_without_a_hit_rate(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(one=lambda: (48, 5, 0, 24, 3))

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(routes_admin, "get_session", get_session)
    response = await routes_admin.analysis_evidence()

    assert response.eligible_matches == 48
    assert response.archive_1_evaluated == 5
    assert response.archive_2_evaluated == 0
    assert response.score_list_evaluated == 24
    assert response.score_list_hits == 3
    assert response.minimum_for_rate == 100
    assert "hit_rate" not in response.model_dump()
    query = session.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    assert "jsonb_exists" in str(query)
    assert "beker" in query.params.values()
