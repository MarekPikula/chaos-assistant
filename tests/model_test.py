"""Data model tests."""
# pylint: disable=W0621

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from chaos_assistant.models.file import ChaosDirectoryModel
from chaos_assistant.models.internal import CategoryIntModel

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_ROOT = Path(__file__).parent.parent / "output"


@pytest.fixture
def example_directory_model():
    """Generate ChaosDirectoryModel from example directory."""
    return ChaosDirectoryModel.from_directory(PROJECT_ROOT / "examples")


@pytest.fixture
def output_root():
    """Create test output root directory."""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return OUTPUT_ROOT


def test_from_directory_model(
    output_root: Path, example_directory_model: ChaosDirectoryModel
):
    """Test CategoryIntModel derivation from ChaosDirectoryModel."""
    result = CategoryIntModel.from_directory_model(example_directory_model)

    with YAML(
        typ="safe", pure=True, output=output_root / "internal_model.yaml"
    ) as yaml:
        yaml.default_flow_style = False
        yaml.dump(result.model_dump(exclude_defaults=True))


# TODO: Add regression test. Needs to set static IDs for that.
