from fastapi import APIRouter, Depends
from src.schemas.recipes import RecipeSearch, RecipeSearchResult
from sqlalchemy.orm import Session
from src.db.deps import get_db
from src.crud.recipes import search_recipes

router = APIRouter(prefix="/recipes")

@router.get("/search", response_model=list[RecipeSearchResult])
def search_endpoint(payload: RecipeSearch = Depends(), db: Session = Depends(get_db)):
    return search_recipes(payload=payload, db=db)