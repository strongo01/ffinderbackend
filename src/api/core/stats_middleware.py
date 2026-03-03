# src/api/core/stats_middleware.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
from .stats_logging import stats_logger

class StatsLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        stats_logger.info(
            "",
            extra={
                "route": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "duration": duration,
            }
        )
        return response