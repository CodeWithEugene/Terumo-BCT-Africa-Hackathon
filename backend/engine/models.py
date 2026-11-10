"""The forecast models the backtest and the app can use, by name."""
from __future__ import annotations

from backend.engine import baseline

REGISTRY = {baseline.NAME: baseline}

try:  # The trained model is added in Step 7. The app must work without it.
    from backend.engine import model_m1

    REGISTRY[model_m1.NAME] = model_m1
except ImportError:  # pragma: no cover
    pass


def get(name: str):
    if name not in REGISTRY:
        raise KeyError(f"Unknown model '{name}'. Choose from: {', '.join(REGISTRY)}")
    return REGISTRY[name]
