"""Smoke tests – verify the package can be imported and exposes a version."""

import anki_auto


def test_import() -> None:
    """The package must be importable."""
    assert anki_auto is not None


def test_version() -> None:
    """The package must expose a non-empty __version__ string."""
    assert isinstance(anki_auto.__version__, str)
    assert anki_auto.__version__ != ""
