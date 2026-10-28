"""Migration zinciri tek başlı olmalı (Sprint 94 M2): iki dalda migration açılırsa `alembic upgrade head` hata verir."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]


def test_alembic_single_head():
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, f"Birden fazla alembic head: {heads} — `alembic merge` gerekli"
