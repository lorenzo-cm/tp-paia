import uuid

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    name: str
    email: EmailStr = Field(index=True, unique=True)


class User(UserBase, table=True):
    hashed_password: str


class UserCreate(UserBase):
    name: str
    password: str
    email: EmailStr
