from fastapi import APIRouter, Depends, HTTPException, status, Request
from src.schemas.recipes import RecipeSearch, RecipeSearchResult, FiltersResult, RecipeResponse, RatingRequest
from sqlalchemy.orm import Session
from src.db.deps import get_db
from src.services.recipes import search_recipes_service, get_all_filters_service, get_recipes_service, rate_recipe_service, RecommendationService
import json
from sqlalchemy import select, text
from src.core.errors import RecipeNotFound

router = APIRouter(prefix="/recipes", tags=["Recipes"])

service = RecommendationService()

@router.get("/search", response_model=list[RecipeSearchResult])
def search_endpoint(payload: RecipeSearch, db: Session = Depends(get_db)):
    return search_recipes_service(payload=payload, db=db)

@router.get("/filters", response_model=FiltersResult)
def filter_endpoint(db: Session = Depends(get_db)):
    return get_all_filters_service(db=db)

@router.get("/{recipe_id}", response_model=RecipeResponse)
def id_endpoint(recipe_id: int, db: Session = Depends(get_db)):
    try:
        return get_recipes_service(db, id=recipe_id)
    except RecipeNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )

@router.post("/rate")
def rating_endpoint(payload: RatingRequest, db: Session = Depends(get_db)):
    with db.begin():
        rate_recipe_service(db=db, payload=payload)

@router.get("/recommendations/{firebase_uid}")
def get_recommendations(firebase_uid: str, request: Request, limit: int = 5, db: Session = Depends(get_db)):
    return service.recommend_for_user(request=request, db=db, firebase_uid=firebase_uid, limit=limit)