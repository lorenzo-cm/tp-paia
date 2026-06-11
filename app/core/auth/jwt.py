from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from app.core.config import get_settings


class JWT:
    def __init__(
        self,
        secret_key: str,
        access_token_expire_minutes: int,
        algorithm: str = "HS256",
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes

    def create_access_token(self, sub: str, data: dict[Any, Any]) -> str:
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "iat": now, "sub": str(sub)})
        encoded_jwt: str = jwt.encode(
            to_encode, self.secret_key, algorithm=self.algorithm
        )
        return encoded_jwt

    def decode_access_token(self, token: str) -> dict[str, Any]:
        payload: dict[Any, Any] = jwt.decode(
            token, self.secret_key, algorithms=[self.algorithm]
        )
        return payload


def get_jwt_instance() -> JWT:
    settings = get_settings()

    return JWT(
        secret_key=settings.JWT_SECRET_KEY,
        access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        algorithm=settings.ALGORITHM,
    )
