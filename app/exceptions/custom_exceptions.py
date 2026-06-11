from fastapi import status


class BaseAppException(Exception):
    def __init__(
        self, title: str, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> None:
        self.title = title
        self.detail = detail
        self.status_code = status_code


class InvalidTokenException(BaseAppException):
    def __init__(self, detail: str = "Invalid token provided.") -> None:
        super().__init__(
            title="Invalid Token",
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InvalidCredentialsException(BaseAppException):
    def __init__(self, detail: str = "Invalid credentials provided.") -> None:
        super().__init__(
            title="Invalid credentials",
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
