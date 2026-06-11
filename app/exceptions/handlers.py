import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .custom_exceptions import BaseAppException

logger = logging.getLogger(__name__)


def init_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.
    """

    @app.exception_handler(BaseAppException)
    async def base_exception_handler(
        request: Request, exc: BaseAppException
    ) -> JSONResponse:
        """
        Handle all exceptions that subclass BaseAIException.
        Returns a JSON response with a consistent error structure.
        """
        return JSONResponse(
            headers={"Content-Type": "application/error+json"},
            status_code=exc.status_code,
            content={
                "title": exc.title,
                "detail": exc.detail,
                "instance": str(request.url),
                "code": exc.status_code,
            },
        )

    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:

        # JWT authentication custom error handling
        if exc.detail == "Not authenticated":
            return JSONResponse(
                headers={"Content-Type": "application/error+json"},
                status_code=exc.status_code,
                content={
                    "title": "Not authenticated",
                    "detail": "You must be ahenticated to access this resource. Try logging in.",
                    "instance": str(request.url.path),
                    "code": "JWT_AUTHENTICATION_ERROR",
                },
            )

        else:
            return JSONResponse(
                headers={"Content-Type": "application/error+json"},
                status_code=exc.status_code,
                content={
                    "title": exc.detail,
                    "detail": exc.detail,
                    "instance": str(request.url.path),
                    "code": "UNSPECICIED_CODE_ERROR",
                },
            )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Fallback for unhandled erros.
        Returns HTTP 500 and a generic message in production.
        """
        logger.exception("Unhandled server error occurred", exc_info=exc)
        return JSONResponse(
            headers={"Content-Type": "application/error+json"},
            status_code=500,
            content={
                "title": "Desculpe, ocorreu algum erro interno, tente novamente",
                "detail": "An unexpected error occurred. Please try again later.",
                "instance": str(request.url),
                "code": "INTERNAL_SERVER_ERROR",
            },
        )
