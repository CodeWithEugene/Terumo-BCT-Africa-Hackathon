"""Shared test set-up: build the database once into a temporary folder."""
import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="sp-test-"))
os.environ["SP_DB_PATH"] = str(_TMP / "app.db")
os.environ.setdefault("SP_SESSION_SECRET", "test-secret")

from backend import config  # noqa: E402  (import after the environment is set)


@pytest.fixture(scope="session")
def db_path() -> Path:
    from backend.pipeline.build import build

    if not config.DB_PATH.exists():
        build(db_path=config.DB_PATH, verbose=False, write_docs=False, run_backtests=False)
    return config.DB_PATH
