from src.crud.recipes import get_all_courses, get_all_kitchens, get_all_tags, search_recipes
from src.schemas.recipes import FiltersResult, RecipeSearch, RecipeSearchResult
from src.db.models import Recipe
from sqlalchemy.orm import Session

def search_recipes_service(db: Session, payload: RecipeSearch):
    rows = search_recipes(payload=payload, db=db)
    return [
        RecipeSearchResult(
            id=row.id,
            title=row.title,
            rank=float(row.rank)
        ) for row in rows
    ]

def get_all_filters(db: Session):
    courses = get_all_courses(db=db)
    kitchens = get_all_kitchens(db=db)
    tags = get_all_tags(db=db)

    return FiltersResult(
        courses=courses,
        kitchens=kitchens,
        tags=tags
    )
