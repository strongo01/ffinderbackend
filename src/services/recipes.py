from src.crud.recipes import get_all_courses, get_all_kitchens, get_all_tags, search_recipes, get_recipe_by_id, rate_recipe, get_user_by_firebase_id, create_user, get_user_interactions
from src.schemas.recipes import FiltersResult, RecipeSearch, RecipeSearchResult, RatingRequest
from src.db.models import Recipe, RecipeInteraction
from sqlalchemy.orm import Session
from src.core.errors import RecipeNotFound
import numpy as np
from src.startup import recipe_matrix, recipe_ids, id_to_index, recipe_cache
from src.db.session import SessionLocal
from fastapi import Request

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

class RecommendationService:

    def recommend_for_user(self, request: Request, db: Session, firebase_uid: str, limit: int = 5):
        matrix = request.app.state.recipe_matrix
        recipe_ids = request.app.state.recipe_ids
        id_to_index = request.app.state.id_to_index
        recipe_cache = request.app.state.recipe_cache

        if matrix is None or recipe_cache is None:
            return []

        interactions = get_user_interactions(db=db, firebase_uid=firebase_uid)

        user_vector = np.zeros(matrix.shape[1])
        rated_indices = []

        for inter in interactions:
            idx = id_to_index.get(inter.recipe_id)
            if idx is not None:
                user_vector += matrix[idx] * (inter.rating or 1.0)
                rated_indices.append(idx)

        if np.linalg.norm(user_vector) == 0:
            return self.cold_start(recipe_cache, limit)

        user_vector /= np.linalg.norm(user_vector)

        scores = matrix @ user_vector
        scores[rated_indices] = -np.inf

        limit = min(limit, len(scores))
        if limit <= 0:
            return []

        top_indices = np.argpartition(scores, -limit)[-limit:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [recipe_cache[recipe_ids[i]] for i in top_indices]

    def cold_start(self, recipe_cache: dict, limit: int = 5):
        import random

        if not recipe_cache:
            return []

        all_ids = list(recipe_cache.keys())
        return [
            recipe_cache[rid]
            for rid in random.sample(all_ids, min(limit, len(all_ids)))
        ]