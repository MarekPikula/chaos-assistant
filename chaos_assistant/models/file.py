"""User-facing file models for Chaos Assistant."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, TypeVar, Union

from loguru import logger
from pydantic import BaseModel, Field, RootModel
from pydantic_yaml import parse_yaml_raw_as

from .user import CategoryModel, LabelModel, Task

SCHEMA_DIR = Path(__file__).parent / "schemas"
"""Directory containing file schemas."""


class ChaosFileModel(ABC, BaseModel):
    """Chaos Assistant configuration file model."""

    @classmethod
    def _export_schema(cls, schema_name: str):
        """Export schema of a model."""
        schema_file_name = SCHEMA_DIR / f"{schema_name}.schema.json"

        logger.info("Exporting {} schema file to {}...", cls.__name__, schema_file_name)
        with open(schema_file_name, "w", encoding="utf8") as schema_file:
            json.dump(cls.model_json_schema(), schema_file, indent=4)

    @classmethod
    @abstractmethod
    def export_schema(cls):
        """Export schema of a label file."""


RootT = TypeVar("RootT", bound=BaseModel)


class LabelsFileModel(ChaosFileModel):
    """File containing label description."""

    labels: List[Union[LabelModel, str]] = Field(
        default_factory=list,
        description="List of labels in current scope.",
    )

    @classmethod
    def export_schema(cls):
        """Export schema of a label file."""
        cls._export_schema("labels")


class CategoryFileModel(ChaosFileModel, RootModel[CategoryModel]):
    """File containing category description."""

    @classmethod
    def export_schema(cls):
        """Export schema of a category file."""
        cls._export_schema("category")


class TaskFileModel(ChaosFileModel, RootModel[Task]):
    """File containing task information."""

    @classmethod
    def export_schema(cls):
        """Export schema of a task file."""
        cls._export_schema("task")


class ChaosDirectory(BaseModel):
    """Chaos Assistant directory."""

    category: CategoryFileModel = Field(
        description="Category description (`category.yaml`)."
    )
    subcategories: List["ChaosDirectory"] = Field(
        default_factory=list,
        description="Subcategories (subdirectories).",
    )
    labels: Optional[LabelsFileModel] = Field(
        None,
        description="Optional label declaration (`labels.yaml` file).",
    )
    tasks: List[TaskFileModel] = Field(
        default_factory=list,
        description="Main tasks (`task-*.yaml` files).",
    )

    @classmethod
    def from_directory(cls, path: Path):
        """Parse directory tree to Chaos Assistant structure.

        Arguments:
            path -- path of the Chaos Assistant configuration.
        """
        if not path.is_dir():
            raise ValueError(f"{path}: Provided path should be directory")

        category_path = list(path.glob("category.y*ml"))
        if len(category_path) != 1:
            raise RuntimeError(f"{path}: Category needs to have a single definition.")

        subcategories_path = list(p for p in path.glob("*") if p.is_dir())

        labels_path = list(path.glob("labels.y*ml"))
        if len(labels_path) > 1:
            raise RuntimeError(
                f'{path}: There should be either "label.yaml" or "label.yml" file.'
            )

        tasks_paths = list(path.glob("task-*.y*ml"))

        return cls(
            category=parse_yaml_raw_as(
                CategoryFileModel, category_path[0].read_text("utf8")
            ),
            subcategories=[
                cls.from_directory(sub_dir) for sub_dir in subcategories_path
            ],
            labels=(
                None
                if len(labels_path) == 0
                else parse_yaml_raw_as(
                    LabelsFileModel, labels_path[0].read_text("utf8")
                )
            ),
            tasks=[
                parse_yaml_raw_as(TaskFileModel, task_file.read_text("utf8"))
                for task_file in tasks_paths
            ],
        )


def export_schemas():
    """Export all file schemas."""
    LabelsFileModel.export_schema()
    CategoryFileModel.export_schema()
    TaskFileModel.export_schema()


if __name__ == "__main__":
    export_schemas()
