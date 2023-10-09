"""Data model tests."""

from pathlib import Path

from chaos_assistant.models.file import ChaosDirectory


def test_from_directory():
    """Test ChaosDirectory.from_directory() with example data."""
    return ChaosDirectory.from_directory(Path(__file__).parent / "../examples")


if __name__ == "__main__":
    result = test_from_directory()
    print(result)
