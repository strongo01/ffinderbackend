from src.db.models import Recipe
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from src.schemas.recipes import RecipeSearchResult, RecipeSearch

def search_recipes(payload: RecipeSearch, db: Session):
    ts_query = func.plainto_tsquery("english", payload.query)
    statement = (select(
        Recipe.id,
        Recipe.title,
        func.ts_rank(Recipe.search_vector, ts_query).label("rank")
    )
    .where(Recipe.search_vector.op("@@")(ts_query))
    .order_by(func.ts_rank(Recipe.search_vector, ts_query).desc())
    .limit(payload.limit)
    .offset(payload.offset))
    results = db.execute(statement)
    return [
        RecipeSearchResult(
            id=row.id,
            title=row.title,
            rank=float(row.rank)
        ) for row in results
    ]