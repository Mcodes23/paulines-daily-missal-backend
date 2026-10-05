from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "data": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        sanitized_errors = []

        for err in exc.errors():
            sanitized_errors.append(
                {
                    "field": ".".join(
                        str(x) for x in err.get("loc", []) if x != "body"
                    ),
                    "message": err.get("msg"),
                    "type": err.get("type"),
                }
            )

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Validation failed",
                "errors": sanitized_errors,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Unexpected error: {str(exc)}",
            },
        )
