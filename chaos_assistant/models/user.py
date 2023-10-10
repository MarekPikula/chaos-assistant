"""User-facing models for Chaos Assistant."""

from datetime import date
from typing import List, Literal, Optional, Union

from pydantic import Field

from .common import ChaosBaseModel, PercentageFloat


class LabelModel(ChaosBaseModel):  # pylint: disable=R0903
    """Item label."""

    @classmethod
    def from_str(cls, s: str):
        """Create label from string."""
        return cls(name=s)  # type: ignore


class WorkItemModel(ChaosBaseModel):  # pylint: disable=R0903
    """Workable item."""

    deadline: Optional[date] = Field(
        None,
        description="Deadline of the work item.",
    )
    labels: List[str] = Field(
        default_factory=list,
        description="List of work item labels. Can be label names or IDs.",
    )


EllipsisTask = Literal["..."]
Task = Union["TaskModel", EllipsisTask, str]


class GroupTaskModel(WorkItemModel):  # pylint: disable=R0903
    """Task with subtasks."""

    subtasks: List[Task] = Field(
        description="List of subtasks.",
    )


class WorkableTaskModel(WorkItemModel):  # pylint: disable=R0903
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

    @classmethod
    def from_str(cls, s: str):
        """Create workable task from string."""
        return cls(name=s)  # type: ignore


TaskModel = Union[GroupTaskModel, WorkableTaskModel]


class CategoryModel(WorkItemModel):  # pylint: disable=R0903
    """Work category."""
