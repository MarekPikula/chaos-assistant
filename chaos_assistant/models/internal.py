"""Internal data representation."""

from datetime import date
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from .user import ChaosBaseModel, LabelModel, PercentageFloat, Task


class WorkItemIntModel(ChaosBaseModel):
    """Workable item (internal)."""

    deadline: Optional[date] = None
    labels: List[LabelModel] = Field(default_factory=list)


class GroupTaskIntModel(WorkItemIntModel):
    """Task with subtasks (internal)."""

    subtasks: List[Task] = Field(default_factory=list)


class WorkableTaskModel(WorkItemIntModel):
    """Task on which a work can be done."""

    complete: Union[PercentageFloat, bool] = Field(False)
    next_slot: Optional[date] = Field(None)
    last_slot: Optional[date] = Field(None)


class EllipsisTaskModel(BaseModel):
    """Internal representation of ellipsis task."""


TaskInt = Union[GroupTaskIntModel, WorkableTaskModel, EllipsisTaskModel]


class CategoryIntModel(WorkItemIntModel):
    """Work category (internal)."""

    subcategories: List["CategoryIntModel"] = Field(default_factory=list)
    tasks: List[TaskInt] = Field(default_factory=list)
