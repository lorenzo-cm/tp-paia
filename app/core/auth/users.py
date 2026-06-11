from app.exceptions.custom_exceptions import InvalidCredentialsException

from .fake_users import FakeUser, fake_users
from .passwords import verify_password


def authenticate_user(email: str, password: str) -> FakeUser:
    user: FakeUser | None = fake_users.get(email)
    if not user or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsException()
    return user
