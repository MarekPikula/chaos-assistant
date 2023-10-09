"""User-facing models for Chaos Assistant."""

from datetime import date
from typing import List, Literal, Optional, Union
from uuid import uuid4

import annotated_types
from pydantic import BaseModel, Field
from typing_extensions import Annotated

PercentageFloat = Annotated[float, annotated_types.Ge(0), annotated_types.Le(100)]


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


EllipsisTask = Literal["..."]


class GroupTaskModel(WorkItemModel):
    """Task with subtasks."""

    subtasks: List[Union["Task", EllipsisTask, str]] = Field(
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
