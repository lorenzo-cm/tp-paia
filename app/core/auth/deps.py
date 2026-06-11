from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.exceptions.custom_exceptions import InvalidTokenException

from .fake_users import FakeUser, fake_users
from .jwt import get_jwt_instance

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> FakeUser:
    try:
        payload: dict[str, Any] = get_jwt_instance().decode_access_token(token)
    except JWTError:
        raise InvalidTokenException() from None

    user_email: str | None = payload.get("email")
    if user_email is None:
        raise InvalidTokenException()

    user = fake_users.get(user_email)
    if user is None:
        raise InvalidTokenException()

    return user
