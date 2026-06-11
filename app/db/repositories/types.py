from typing import Protocol, TypeVar, runtime_checkable
from uuid import UUID

from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateType = TypeVar("CreateType", bound=SQLModel)
UpdateType = TypeVar("UpdateType", bound=SQLModel)
IdType = TypeVar("IdType", UUID, int)


@runtime_checkable
class HasId(Protocol[IdType]):
    id: IdType
