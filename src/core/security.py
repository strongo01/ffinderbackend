import os
from fastapi import Request, Depends
from fastapi.security import APIKeyHeader
from src.core.errors import InvalidAppKey

APP_KEY = os.getenv("APP_KEY")
api_key_header = APIKeyHeader(name="x-app-key", auto_error=False)

async def verify_app_key(api_key: str = Depends(api_key_header)):
    if not api_key or api_key != APP_KEY:
        from src.core.errors import InvalidAppKey
        raise InvalidAppKey()
    return api_key