from fastapi import APIRouter
from src.schemas.health import HealthOk

router = APIRouter(prefix="/health")

@router.get("")
def health():
    return HealthOk()