"""The error contract — API.md §1.

Every error the API returns has the same shape:

    {"detail": {"code": "MEMBER_HAS_ACTIVE_LOAN", "message": "…"}}

so the frontend has exactly one error path. Services raise ApiError; the
handlers registered here do the rest.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def unauthenticated(message: str = "Authentication required.") -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", message)


def forbidden(message: str = "You do not have permission to do that.") -> ApiError:
    return ApiError(403, "FORBIDDEN", message)


def not_found(message: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", message)


def duplicate_field(message: str) -> ApiError:
    return ApiError(409, "DUPLICATE_FIELD", message)


def invalid_state(message: str) -> ApiError:
    return ApiError(409, "INVALID_STATE", message)


def invalid_date(message: str) -> ApiError:
    return ApiError(422, "INVALID_DATE", message)


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "fields": fields,
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        # Defensive net: services pre-check duplicates, but if a race slips
        # through we still return the contract, never a stack trace.
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": "DUPLICATE_FIELD",
                    "message": "The request conflicts with existing data.",
                }
            },
        )
