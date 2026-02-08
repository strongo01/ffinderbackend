from fastapi import APIRouter, Depends
from src.schemas.health import HealthOk
from sqlalchemy.orm import Session
from src.db.deps import get_db
from sqlalchemy import text

router = APIRouter(prefix="/health")

@router.get("", response_model=HealthOk)
def health():
    return HealthOk()

@router.get("/db", response_model=HealthOk)
def db_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return HealthOk()