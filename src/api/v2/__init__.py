from fastapi import APIRouter
from .routers import routers

router = APIRouter(prefix="/v2")

for rtr in routers:
    router.include_router(rtr)