"""Chaos Assistant CLI tool."""

import sys
from pathlib import Path

import click
from loguru import logger
from pydantic import ValidationError
from ruamel.yaml.scanner import ScannerError

from .models.common import ChaosKeyError, ChaosLookupError
from .models.file import ChaosDirectoryModel
from .models.internal import CategoryIntModel


@click.group()
@click.argument(
    "CHAOS", type=click.Path(exists=True, file_okay=False, path_type=Path), required=1
)
@click.pass_context
def main(ctx: click.Context, chaos: Path):
    """Chaos Assistant TODO app for chaotic project management.

    CHAOS: Directory containing Chaos
    """
    logger.info("Loading {} Chaos directory.", chaos)
    try:
        user_model = ChaosDirectoryModel.from_directory(chaos)
        internal_model = CategoryIntModel.from_directory_model(user_model)
    except ScannerError as ruamel_err:
        logger.error("Failed to load YAML file: {}", ruamel_err)
        sys.exit(-1)
    except ValidationError as pydantic_err:
        logger.error("Validation error during parsing of Chaos directory:")
        for details in pydantic_err.errors():
            logger.error(
                '  {} {}: {} (caused by value: "{}")',
                details["type"],
                ":".join(str(loc) for loc in details["loc"]),
                details["msg"],
                details["input"],
            )
        sys.exit(-1)
    except ChaosLookupError as lookup_err:
        logger.error("Failed to find {}: {}", lookup_err.subject, lookup_err.key)
        sys.exit(-1)
    except ChaosKeyError as lookup_err:
        logger.error("Duplicate {}: {}", lookup_err.subject, lookup_err.key)
        sys.exit(-1)

    ctx.ensure_object(dict)
    ctx.obj["internal"] = internal_model


@main.command()
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    help="Output path for the YAML file.",
)
@click.pass_context
def export_internal(ctx: click.Context, output: Path):
    """Export internal representation."""
    internal_model = ctx.obj["internal"]
    assert isinstance(internal_model, CategoryIntModel)

    logger.info("Exporting internal model to: {}", output)

    try:
        internal_model.export_yaml(output)
    except Exception as err:  # pylint: disable=W0718
        logger.error("Error occurred during YAML export: {}", err)
        sys.exit(-1)
