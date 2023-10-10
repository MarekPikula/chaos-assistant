"""Internal data representation."""

import dataclasses
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field, RootModel
from ruamel.yaml import YAML

from .common import (
    ChaosBaseModel,
    ChaosLookup,
    ItemPath,
    PercentageFloat,
    TidStr,
    TypedModel,
)
from .file import ChaosDirectoryModel
from .user import GroupTaskModel, LabelModel, Task, WorkableTaskModel


@dataclass
class ParentScope:
    """Parent item scope.

    Used for recursive item tree creation.
    """

    tid: TidStr
    """Parent typed ID."""

    path: ItemPath
    """Parent path."""

    label_scope: "LabelLookupScope"
    """Parent label scope."""

    uuid_lookup: "IdLookup"
    """Parent/global ID lookup."""


class LabelIntModel(LabelModel, TypedModel):
    """Label model (internal)."""

    _tid_prefix = "L"

    @classmethod
    def from_user_model(cls, label: LabelModel):
        """Create internal model from user model (from file)."""
        return cls(tid=cls.generate_tid(label.id), **label.model_dump())


class WorkItemIntModel(ChaosBaseModel, TypedModel):
    """Workable item (internal)."""

    parent_tid: Optional[TidStr] = Field(
        None, description="Typed ID of the parent node."
    )
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

    _tid_prefix = "T"

    @classmethod
    def from_user_model(cls, parent: ParentScope, file_model: GroupTaskModel):
        """Create internal model from user model (from file)."""
        cur_scope = dataclasses.replace(
            parent,
            tid=cls.generate_tid(file_model.id),
            path=parent.path / file_model.name,
        )
        parent.uuid_lookup.add_dummy(file_model.id)

        file_model_dict = file_model.model_dump()
        file_model_dict["labels"] = list(parent.label_scope.get_iter(file_model.labels))
        file_model_dict["subtasks"] = list(
            cls.task_from_file_model(cur_scope, task) for task in file_model.subtasks
        )

        ret = cls(
            tid=cur_scope.tid,
            parent_tid=parent.tid,
            path=cur_scope.path,
            **file_model_dict,
        )
        parent.uuid_lookup.add(ret, overwrite=True)
        return ret


class WorkableTaskIntModel(WorkItemIntModel):
    """Task on which a work can be done."""

    complete: Union[PercentageFloat, bool] = False
    next_slot: Optional[date] = None
    last_slot: Optional[date] = None

    _tid_prefix = "W"

    @classmethod
    def from_user_model(cls, parent: ParentScope, file_model: WorkableTaskModel):
        """Create internal model from user model (from file)."""
        cur_path = parent.path / file_model.name

        file_model_dict = file_model.model_dump()
        file_model_dict["labels"] = list(parent.label_scope.get_iter(file_model.labels))

        ret = cls(
            tid=cls.generate_tid(file_model.id),
            parent_tid=parent.tid,
            path=cur_path,
            **file_model_dict,
        )
        parent.uuid_lookup.add(ret)
        return ret


class EllipsisTaskModel(RootModel[str]):  # pylint: disable=R0903
    """Internal representation of ellipsis task."""

    root: str = "..."


TaskInt = Union[GroupTaskIntModel, WorkableTaskIntModel, EllipsisTaskModel]
"""Internal task representation."""

LookupModels = Union[
    LabelIntModel, GroupTaskIntModel, WorkableTaskIntModel, "CategoryIntModel"
]
"""Models which can be looked up (with UUID)."""

LabelLookupScope = ChaosLookup[LabelIntModel]
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

    _tid_prefix = "C"

    @classmethod
    def from_directory_model(
        cls, dir_model: ChaosDirectoryModel, parent: Optional[ParentScope] = None
    ):
        """Create category from directory model."""
        category = dir_model.category.root

        cur_scope = ParentScope(
            cls.generate_tid(category.id),
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
                LabelIntModel.from_user_model(LabelModel.from_str(label))
                if isinstance(label, str)
                else LabelIntModel.from_user_model(label)
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
            tid=cls.generate_tid(category.id),
            parent_tid=None if parent is None else parent.tid,
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

    def export_yaml(self, output_path: Path):
        """Dump YAML representation of the full tree.

        Arguments:
            output_path -- path to the output file.

        Raises:
            ValueError: wrong path format.
        """
        if output_path.is_dir():
            raise ValueError("Output path cannot be a directory")
        if not (
            output_path.name.endswith(".yaml") or output_path.name.endswith(".yml")
        ):
            raise ValueError("Output file needs to have .yaml extension.")

        with YAML(typ="safe", pure=True, output=output_path) as yaml:
            yaml.default_flow_style = False
            yaml.dump(self.model_dump(exclude_defaults=True))
