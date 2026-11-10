"""The product uses no donor or patient identities. This test keeps it that way."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
# Built from two parts so this test file itself never names the file in one piece.
FORBIDDEN = "donors" + ".csv"


def test_backend_never_references_the_donor_file():
    offenders = [
        str(path.relative_to(BACKEND.parent))
        for path in BACKEND.rglob("*.py")
        if FORBIDDEN in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"These files mention {FORBIDDEN}: {offenders}"


def test_donor_file_is_not_in_the_repo():
    assert not (BACKEND.parent / "data" / "raw" / FORBIDDEN).exists()
