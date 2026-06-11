from abc import ABC
from typing import Any, Generic, Literal, overload

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.db.repositories.exceptions import (
    RepositoryCreationError,
    RepositoryDeleteError,
    RepositoryNotFoundError,
    RepositoryUpdateError,
)
from app.db.repositories.types import CreateType, HasId, IdType, ModelType, UpdateType


class BaseRepository(ABC, Generic[ModelType, CreateType, UpdateType, IdType]):
    def __init__(self, db: Session, model: type[ModelType]):
        self.db = db
        self.model = model

    @overload
    def get(self, id: IdType, raise_exception: Literal[True]) -> ModelType: ...

    @overload
    def get(self, id: IdType, raise_exception: Literal[False] = False) -> ModelType | None: ...

    def get(self, id: IdType, raise_exception: bool = False) -> ModelType | None:
        entity = self.db.get(self.model, id)
        if raise_exception and entity is None:
            raise RepositoryNotFoundError(f"{self.model.__name__} {id} not found")
        return entity

    def create(self, create_model: CreateType, *, flush: bool = True) -> ModelType:
        try:
            db_obj = self.model.model_validate(create_model)
            self.db.add(db_obj)
            if flush:
                self.db.flush()
                self.db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as exc:
            raise RepositoryCreationError(
                f"Failed to create {self.model.__name__}: {exc}"
            ) from exc

    def update(
        self,
        update_data: UpdateType | ModelType | HasId[IdType],
        *,
        exclude_none: bool = True,
        flush: bool = True,
    ) -> ModelType:
        try:
            entity = self.get(update_data.id, raise_exception=True)

            dump_kwargs: dict[str, Any] = {"exclude_unset": True, "exclude": {"id"}}
            if exclude_none:
                dump_kwargs["exclude_none"] = True
            values = update_data.model_dump(**dump_kwargs)

            for key, value in values.items():
                setattr(entity, key, value)

            self.db.add(entity)
            if flush:
                self.db.flush()
                self.db.refresh(entity)
            return entity
        except SQLAlchemyError as exc:
            raise RepositoryUpdateError(
                f"Failed to update {self.model.__name__}: {exc}"
            ) from exc

    def delete(self, entity: ModelType, *, flush: bool = True) -> None:
        try:
            self.db.delete(entity)
            if flush:
                self.db.flush()
        except SQLAlchemyError as exc:
            raise RepositoryDeleteError(
                f"Failed to delete {self.model.__name__}: {exc}"
            ) from exc

    def commit(self) -> None:
        self.db.commit()
