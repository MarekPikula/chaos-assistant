"""Internal data representation."""

import dataclasses
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Union

from pydantic import Field, RootModel

from .common import ChaosBaseModel, ChaosLookup, IdStr, ItemPath, PercentageFloat
from .file import ChaosDirectoryModel
from .user import GroupTaskModel, LabelModel, Task, WorkableTaskModel


@dataclass
class ParentScope:
    """Parent item scope.

    Used for recursive item tree creation.
    """

    id: IdStr
    """Parent ID."""

    path: ItemPath
    """Parent path."""

    label_scope: "LabelLookupScope"
    """Parent label scope."""

    uuid_lookup: "IdLookup"
    """Parent/global ID lookup."""


class WorkItemIntModel(ChaosBaseModel):
    """Workable item (internal)."""

    parent_id: Optional[IdStr] = Field(None, description="ID of the parent node.")
    path: ItemPath = Field(..., description="Path of the item.")

    deadline: Optional[date] = None
    labels: List[LabelModel] = Field(default_factory=list)

    @staticmethod
    def task_from_file_model(parent: ParentScope, task: Task) -> "TaskInt":
        """Create task from generic Task."""
        if isinstance(task, GroupTaskModel):
            return GroupTaskIntModel.from_user_model(parent, task)
        if isinstance(task, WorkableTaskModel):
            return WorkableTaskIntModel.from_user_model(parent, task)
        if task == "...":
            return EllipsisTaskModel()
        assert isinstance(task, str)
        return WorkableTaskIntModel.from_user_model(
            parent, WorkableTaskModel.from_str(task)
        )


class GroupTaskIntModel(WorkItemIntModel):
    """Task with subtasks (internal)."""

    subtasks: List["TaskInt"] = Field(default_factory=list)

    @classmethod
    def from_user_model(
        cls, parent: ParentScope, file_model: GroupTaskModel
    ) -> "GroupTaskIntModel":
        """Create internal model from user model (from file)."""
        cur_scope = dataclasses.replace(
            parent, id=file_model.id, path=parent.path / file_model.name
        )
        parent.uuid_lookup.add_dummy(file_model.id)

        file_model_dict = file_model.model_dump()
        file_model_dict["labels"] = list(parent.label_scope.get_iter(file_model.labels))
        file_model_dict["subtasks"] = list(
            cls.task_from_file_model(cur_scope, task) for task in file_model.subtasks
        )

        ret = cls(parent_id=parent.id, path=cur_scope.path, **file_model_dict)
        parent.uuid_lookup.add(ret, overwrite=True)
        return ret


class WorkableTaskIntModel(WorkItemIntModel):
    """Task on which a work can be done."""

    complete: Union[PercentageFloat, bool] = False
    next_slot: Optional[date] = None
    last_slot: Optional[date] = None

    @classmethod
    def from_user_model(
        cls, parent: ParentScope, file_model: WorkableTaskModel
    ) -> "WorkableTaskIntModel":
        """Create internal model from user model (from file)."""
        cur_path = parent.path / file_model.name

        file_model_dict = file_model.model_dump()
        file_model_dict["labels"] = list(parent.label_scope.get_iter(file_model.labels))

        ret = cls(parent_id=parent.id, path=cur_path, **file_model_dict)
        parent.uuid_lookup.add(ret)
        return ret


class EllipsisTaskModel(RootModel[str]):  # pylint: disable=R0903
    """Internal representation of ellipsis task."""

    root: str = "..."


TaskInt = Union[GroupTaskIntModel, WorkableTaskIntModel, EllipsisTaskModel]
"""Internal task representation."""

LookupModels = Union[
    LabelModel, GroupTaskIntModel, WorkableTaskIntModel, "CategoryIntModel"
]
"""Models which can be looked up (with UUID)."""

LabelLookupScope = ChaosLookup[LabelModel]
"""Lookup of labels within the current scope."""

IdLookup = ChaosLookup[LookupModels]
"""Global lookup of UUIDs."""


class CategoryIntModel(WorkItemIntModel):
    """Work category (internal).

    Used as a root model.
    """

    # Needed for label_lookup and id_lookup.
    model_config = {"arbitrary_types_allowed": True}

    subcategories: List["CategoryIntModel"] = Field(default_factory=list)
    tasks: List[TaskInt] = Field(default_factory=list)

    # Internal scope and lookup fields.
    label_scope: LabelLookupScope = Field(exclude=True)
    uuid_lookup: IdLookup = Field(exclude=True)

    @classmethod
    def from_directory_model(
        cls, dir_model: ChaosDirectoryModel, parent: Optional[ParentScope] = None
    ):
        """Create category from directory model."""
        category = dir_model.category.root

        cur_scope = ParentScope(
            category.id,
            (ItemPath() if parent is None else parent.path) / category.name,
            LabelLookupScope(
                "label",
                None if parent is None else parent.label_scope,
                index_by_name=True,
            ),
            IdLookup("id") if parent is None else parent.uuid_lookup,
        )

        local_labels = (
            list(
                LabelModel.from_str(label) if isinstance(label, str) else label
                for label in dir_model.labels.labels
            )
            if dir_model.labels is not None
            else []
        )
        cur_scope.label_scope.add_iter(local_labels)
        cur_scope.uuid_lookup.add_iter(local_labels)

        category_dict = category.model_dump()
        category_dict["labels"] = list(cur_scope.label_scope.get_iter(category.labels))

        cur_scope.uuid_lookup.add_dummy(category.id)
        ret = cls(
            parent_id=None if parent is None else parent.id,
            path=cur_scope.path,
            subcategories=[
                cls.from_directory_model(subdir, cur_scope)
                for subdir in dir_model.subcategories
            ],
            tasks=[
                cls.task_from_file_model(cur_scope, task.root)
                for task in dir_model.tasks
            ],
            label_scope=cur_scope.label_scope,
            uuid_lookup=cur_scope.uuid_lookup,
            **category_dict,
        )
        cur_scope.uuid_lookup.add(ret, overwrite=True)

        return ret
