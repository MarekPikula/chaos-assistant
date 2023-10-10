"""Internal data representation."""

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
    TidPrefixEnum,
    TypedModel,
)
from .file import ChaosDirectoryModel
from .user import GroupTaskModel, LabelModel, Task, WorkableTaskModel


class LabelIntModel(LabelModel, TypedModel):
    """Label model (internal)."""

    _tid_prefix = TidPrefixEnum.LABEL

    @classmethod
    def from_user_model(cls, label: LabelModel):
        """Create internal model from user model (from file)."""
        return cls(tid=cls.generate_tid(label.id), **label.model_dump())


LabelLookupScope = ChaosLookup[LabelIntModel]
"""Lookup of labels within the current scope."""

IdLookup = ChaosLookup["LookupModels"]
"""Global lookup of UUIDs."""


class WorkItemIntModel(ChaosBaseModel, TypedModel):
    """Workable item (internal)."""

    # Needed for label_lookup and id_lookup.
    model_config = {"arbitrary_types_allowed": True}

    path: ItemPath = Field(..., description="Path of the item.")
    # TODO: Make the path a cacheable property.

    deadline: Optional[date] = None
    labels: List[LabelModel] = Field(default_factory=list)

    # Internal scope and lookup fields.
    parent: Optional["WorkItemIntModel"] = Field(
        description="Parent of the node.", exclude=True
    )
    label_scope: LabelLookupScope = Field(
        description="Label lookup scope.", exclude=True
    )
    uuid_lookup: IdLookup = Field(
        description="Global UUID lookup reference", exclude=True
    )

    @staticmethod
    def task_from_file_model(parent: "WorkItemIntModel", task: Task) -> "TaskInt":
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

    _tid_prefix = TidPrefixEnum.GROUP_TASK

    @classmethod
    def from_user_model(cls, parent: WorkItemIntModel, file_model: GroupTaskModel):
        """Create internal model from user model (from file)."""
        file_model_dict = file_model.model_dump()
        file_model_dict["labels"] = list(parent.label_scope.get_iter(file_model.labels))
        file_model_dict["subtasks"] = []

        parent.uuid_lookup.add_dummy(file_model.id)
        ret = cls(
            tid=cls.generate_tid(file_model.id),
            parent=parent,
            label_scope=parent.label_scope,
            uuid_lookup=parent.uuid_lookup,
            path=parent.path / file_model.name,
            **file_model_dict,
        )
        ret.subtasks = list(
            cls.task_from_file_model(ret, task) for task in file_model.subtasks
        )
        parent.uuid_lookup.add(ret, overwrite=True)
        return ret


class WorkableTaskIntModel(WorkItemIntModel):
    """Task on which a work can be done."""

    complete: Union[PercentageFloat, bool] = False
    next_slot: Optional[date] = None
    last_slot: Optional[date] = None

    _tid_prefix = TidPrefixEnum.WORKABLE_TASK

    @classmethod
    def from_user_model(cls, parent: WorkItemIntModel, file_model: WorkableTaskModel):
        """Create internal model from user model (from file)."""
        file_model_dict = file_model.model_dump()
        file_model_dict["labels"] = list(parent.label_scope.get_iter(file_model.labels))

        ret = cls(
            tid=cls.generate_tid(file_model.id),
            parent=parent,
            label_scope=parent.label_scope,
            uuid_lookup=parent.uuid_lookup,
            path=parent.path / file_model.name,
            **file_model_dict,
        )
        parent.uuid_lookup.add(ret)
        return ret


LookupModels = Union[
    LabelIntModel, GroupTaskIntModel, WorkableTaskIntModel, "CategoryIntModel"
]
"""Models which can be looked up (with UUID)."""


class EllipsisTaskModel(RootModel[str]):  # pylint: disable=R0903
    """Internal representation of ellipsis task."""

    root: str = "..."


TaskInt = Union[GroupTaskIntModel, WorkableTaskIntModel, EllipsisTaskModel]
"""Internal task representation."""


class CategoryIntModel(WorkItemIntModel):
    """Work category (internal).

    Used as a root model.
    """

    subcategories: List["CategoryIntModel"] = Field(default_factory=list)
    tasks: List[TaskInt] = Field(default_factory=list)

    _tid_prefix = TidPrefixEnum.CATEGORY

    @classmethod
    def from_directory_model(
        cls, dir_model: ChaosDirectoryModel, parent: Optional[WorkItemIntModel] = None
    ):
        """Create category from directory model."""
        category = dir_model.category.root

        label_scope = LabelLookupScope(
            "label",
            None if parent is None else parent.label_scope,
            index_by_name=True,
        )

        uuid_lookup = IdLookup("id") if parent is None else parent.uuid_lookup

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
        label_scope.add_iter(local_labels)
        uuid_lookup.add_iter(local_labels)

        category_dict = category.model_dump()
        category_dict["labels"] = list(label_scope.get_iter(category.labels))

        uuid_lookup.add_dummy(category.id)
        ret = cls(
            tid=cls.generate_tid(category.id),
            parent=parent,
            path=(ItemPath() if parent is None else parent.path) / category.name,
            subcategories=[],
            tasks=[],
            label_scope=label_scope,
            uuid_lookup=uuid_lookup,
            **category_dict,
        )
        ret.subcategories = [
            cls.from_directory_model(subdir, ret) for subdir in dir_model.subcategories
        ]
        ret.tasks = [
            cls.task_from_file_model(ret, task.root) for task in dir_model.tasks
        ]
        uuid_lookup.add(ret, overwrite=True)

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
