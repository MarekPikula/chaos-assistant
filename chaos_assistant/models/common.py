"""Utilities and common classes used for data models."""

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import ClassVar, Dict, Generic, Iterable, Optional, TypeVar, Union
from uuid import uuid4

import annotated_types
from pydantic import BaseModel, Field
from pydantic.types import StringConstraints
from typing_extensions import Annotated

PercentageFloat = Annotated[float, annotated_types.Ge(0), annotated_types.Le(100)]
"""Float representing percentage 0-100%."""

IdStr = Annotated[
    str, StringConstraints(pattern=r"^[^/.\s]+$", strip_whitespace=True, to_lower=True)
]
"""String representing ID.

Stripped from whitespaces, lowercase, cannot contain whitespaces and slashes.
"""

TidStr = Annotated[str, StringConstraints(pattern=r"^[LTWC]-[^/.\s]+$")]
"""String representing typed ID.

Typed ID is normal ID (IdStr) with type prefix.
"""

NameStr = Annotated[str, StringConstraints(pattern=r"^[^/\n]+$")]
"""String representing item name.

Cannot contain slashes.
"""


class TidPrefixEnum(Enum):
    """Typed ID prefixes."""

    LABEL = "L"
    GROUP_TASK = "T"
    WORKABLE_TASK = "W"
    CATEGORY = "C"


class ChaosBaseModel(ABC, BaseModel):
    """Base model for all Chaos items."""

    id: IdStr = Field(
        default_factory=lambda: uuid4().hex,
        description=(
            "ID of the element. Can be any kind of string, but if not provided UUID4 "
            "will be used. Needs to be unique within the scope of the item."
        ),
    )
    name: NameStr = Field(
        description="Name of the item.",
    )
    desc: Optional[str] = Field(
        None,
        description=(
            "Description of the item. Can be provided as Markdown within the YAML file."
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

    _tid_prefix: ClassVar[TidPrefixEnum]
    """Typed ID prefix letter."""

    @classmethod
    def generate_tid(cls, source_id: IdStr) -> TidStr:
        """Generate typed ID from regular ID."""
        return f"{cls._tid_prefix.value}-{source_id}"

    @cached_property
    def tid(self) -> TidStr:
        """Get typed ID of the item."""
        return self.generate_tid(self.id)


@dataclass
class BaseChaosLookupError(Exception):
    """Base lookup error."""

    msg: str
    subject: str
    scope: Path
    key: str


class ChaosKeyError(BaseChaosLookupError, KeyError):
    """Error during item add (key collision)."""


class ChaosLookupError(BaseChaosLookupError, KeyError):
    """Error during key lookup."""


LookupT = TypeVar("LookupT", bound=ChaosBaseModel)


class ChaosLookup(Generic[LookupT]):
    """Chaos item lookup."""

    def __init__(
        self,
        subject: str,
        base: Optional[
            Union[Dict[str, Optional[LookupT]], "ChaosLookup[LookupT]"]
        ] = None,
        index_by_name: bool = False,
        scope: Path = Path("/"),
    ):
        """Construct item lookup.

        Arguments:
            subject -- lookup subject. Used in exception messages.

        Keyword Arguments:
            base -- existing lookup (copied) on which we want to base (default: {None})
            index_by_name -- by default lookup is indexed only on UUID. With this option
                enabled, name is also used as index (default: {False})
            scope -- scope of this lookup (default: root scope)
        """
        self._subject = subject.lower()
        self._index_by_name = index_by_name
        self._scope = scope

        if base is None:
            self._table = {}
        elif isinstance(base, ChaosLookup):
            self._table = base.dict()
        else:
            self._table = base.copy()

    def add(self, item: LookupT, overwrite: bool = False):
        """Add item to lookup.

        Arguments:
            item -- lookup Chaos item.

        Keyword Arguments:
            overwrite -- overwrite dummy item if exists (default: {False})

        Raises:
            ChaosKeyError: Key already exists in the current scope.
        """
        if item.tid in self._table.keys() and (
            not overwrite or self._table[item.tid] is not None
        ):
            raise ChaosKeyError(
                f'{self._subject.capitalize()} "{item.tid}" '
                f'already exists in the "{self._scope}" lookup scope.',
                self._subject,
                self._scope,
                item.tid,
            )

        if (
            self._index_by_name
            and item.name in self._table.keys()
            and (not overwrite or self._table[item.name] is not None)
        ):
            raise ChaosKeyError(
                f'{self._subject.capitalize()} name "{item.name}" '
                f'already exists in the "{self._scope}" lookup scope.',
                self._subject,
                self._scope,
                item.name,
            )

        self._table[item.tid] = item
        if self._index_by_name:
            self._table[item.name] = item

    def add_dummy(self, key: str):
        """Add dummy key to the index.

        Useful if generating tree-like structure with leafs being created with root not
        fully initialized.

        Arguments:
            key -- dummy key to register.

        Raises:
            ChaosKeyError: Key already exists in the current scope.
        """
        if key in self._table.keys():
            raise ChaosKeyError(
                f'{self._subject.capitalize()} "{key}" '
                f'already exists in the "{self._scope}" lookup scope.',
                self._subject,
                self._scope,
                key,
            )

        self._table[key] = None

    def add_iter(self, items: Iterable[LookupT]):
        """Add multiple items at the same time.

        Arguments:
            items -- iterable with items to add.
        """
        for it in items:
            self.add(it)

    def get(self, key: str) -> LookupT:
        """Lookup an item with a key.

        Arguments:
            key -- lookup key.

        Raises:
            ChaosLookupError: Item not found or only dummy item exists.

        Returns:
            Item if it is found.
        """
        ret = self._table.get(key)
        if ret is None:
            raise ChaosLookupError(
                f'No {self._subject} with key "{key}" exists in the current scope.',
                self._subject,
                self._scope,
                key,
            )
        return ret

    def get_iter(self, keys: Iterable[str]) -> Iterable[LookupT]:
        """Lookup multiple items."""
        return (self.get(key) for key in keys)

    def get_type(self, key_type: TidPrefixEnum) -> Iterable[LookupT]:
        """Get items of the given type."""
        return (
            item
            for key, item in self._table.items()
            if key.startswith(key_type.value) and item is not None
        )

    def is_dummy(self, key: str) -> bool:
        """Check if given key is dummy."""
        return key in self._table.keys() and self._table[key] is None

    def dict(self) -> Dict[str, Optional[LookupT]]:
        """Get copy of internal lookup table."""
        return self._table.copy()
