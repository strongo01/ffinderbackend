from fastapi import APIRouter, Depends
from src.schemas.recipes import RecipeSearch, RecipeSearchResult, FiltersResult
from sqlalchemy.orm import Session
from src.db.deps import get_db
from src.crud.recipes import search_recipes
from src.services.recipes import get_all_filters
import json
from sqlalchemy import select, text

router = APIRouter(prefix="/recipes")

@router.get("/search", response_model=list[RecipeSearchResult])
def search_endpoint(payload: RecipeSearch = Depends(), db: Session = Depends(get_db)):
    return search_recipes(payload=payload, db=db)

@router.get("/filters", response_model=FiltersResult)
def filter_endpoint(db: Session = Depends(get_db)):
    return get_all_filters(db=db)