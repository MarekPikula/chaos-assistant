"""User-facing models for Chaos Assistant."""

import json
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import List, Literal, Optional, TypeVar, Union
from uuid import uuid4

import annotated_types
from loguru import logger
from pydantic import BaseModel, Field, RootModel
from typing_extensions import Annotated

SCHEMA_DIR = Path(__file__).parent / "schemas"
"""Directory containing file schemas."""

# Custom Pydantic types


PercentageFloat = Annotated[float, annotated_types.Ge(0), annotated_types.Le(100)]


# Data models


class ChaosBaseModel(BaseModel):
    """Base model for all Chaos items."""

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description=(
            "ID of the element. "
            "Can be any kind of string, but if not provided UUID4 will be used. "
            "Needs to be unique within the scope of the item."
        ),
    )
    name: str = Field(
        description="Name of the item.",
    )
    desc: Optional[str] = Field(
        None,
        description=(
            "Description of the item. "
            "Can be provided as Markdown within the YAML file."
        ),
    )
    enabled: bool = Field(
        True,
        description="If the item is enabled.",
    )
    priority: int = Field(
        1,
        ge=0,
        description="Priority of the item. Normalized at the item's level.",
    )


class LabelModel(ChaosBaseModel):
    """Item label."""


class WorkItemModel(ChaosBaseModel):
    """Workable item."""

    deadline: Optional[date] = Field(
        None,
        description="Deadline of the work item.",
    )
    labels: List[str] = Field(
        default_factory=list,
        description="List of work item labels. Can be label names or IDs.",
    )


class CategoryModel(WorkItemModel):
    """Work category."""

    subcategories: Optional[List["CategoryModel"]] = Field(
        None,
        description=(
            "List of subcategories. Can be either in-file list or a directory tree."
        ),
    )
    tasks: Optional[List["Task"]] = Field(
        None,
        description=(
            "List of tasks. "
            "Can be either in-file list or files in the category directory."
        ),
    )


class GroupTaskModel(WorkItemModel):
    """Task with subtasks."""

    subtasks: List[Union["Task", str, Literal["..."]]] = Field(
        description="List of subtasks.",
    )


class WorkableTaskModel(WorkItemModel):
    """Task on which a work can be done."""

    complete: Union[PercentageFloat, bool] = Field(
        False,
        description="Level of task completeness.",
    )
    next_slot: Optional[date] = Field(
        None,
        description="Next work slot.",
    )
    last_slot: Optional[date] = Field(
        None,
        description="Last time the task was worked on.",
    )


Task = Union[GroupTaskModel, WorkableTaskModel]


# File models


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


class ChaosFileWithDescModelMixin(
    RootModel[Union[RootT, str]]
):  # pylint: disable=R0903
    """Chaos Assistant configuration file model with markdown description."""


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


class CategoryFileModel(ChaosFileModel, ChaosFileWithDescModelMixin[CategoryModel]):
    """File containing category description."""

    @classmethod
    def export_schema(cls):
        """Export schema of a category file."""
        cls._export_schema("category")


class TaskFileModel(ChaosFileModel, ChaosFileWithDescModelMixin[Task]):
    """File containing task information."""

    @classmethod
    def export_schema(cls):
        """Export schema of a task file."""
        cls._export_schema("task")


def export_schemas():
    """Export all file schemas."""
    LabelsFileModel.export_schema()
    CategoryFileModel.export_schema()
    TaskFileModel.export_schema()


if __name__ == "__main__":
    export_schemas()
