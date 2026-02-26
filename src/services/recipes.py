from src.crud.recipes import get_all_courses, get_all_kitchens, get_all_tags, search_recipes, get_recipe_by_id, rate_recipe, get_user_by_firebase_id, create_user
from src.schemas.recipes import FiltersResult, RecipeSearch, RecipeSearchResult, RatingRequest
from src.db.models import Recipe
from sqlalchemy.orm import Session
from src.core.errors import RecipeNotFound

def search_recipes_service(db: Session, payload: RecipeSearch):
    rows = search_recipes(payload=payload, db=db)
    return [
        RecipeSearchResult(
            id=row.id,
            title=row.title,
            rank=float(row.rank)
        ) for row in rows
    ]

def get_all_filters_service(db: Session):
    courses = get_all_courses(db=db)
    kitchens = get_all_kitchens(db=db)
    tags = get_all_tags(db=db)

    return FiltersResult(
        courses=courses,
        kitchens=kitchens,
        tags=tags
    )

def get_recipes_service(db: Session, id: int):
    results =  get_recipe_by_id(db, id=id)
    if results is None:
        raise RecipeNotFound()
    return results

def rate_recipe_service(db: Session, payload: RatingRequest):
    user = get_user_by_firebase_id(firebase_uid=payload.firebase_uid, db=db)
    if not user:
        user = create_user(firebase_uid=payload.firebase_uid, db=db)
    rate_recipe(user_id=user.id, recipe_id=payload.recipe_id, rating=payload.rating, db=db)
