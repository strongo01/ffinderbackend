from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from .error_logging import error_logger
import traceback

class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            tb = traceback.format_exc()
            error_logger.error(
                f"Exception on {request.method} {request.url}:\n{tb}"
            )
            raise