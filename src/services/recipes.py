from src.crud.recipes import get_all_courses, get_all_kitchens, get_all_tags, search_recipes, get_recipe_by_id
from src.schemas.recipes import FiltersResult, RecipeSearch, RecipeSearchResult
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