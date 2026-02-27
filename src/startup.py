import numpy as np
import pickle
from sqlalchemy.orm import joinedload
from src.db.session import SessionLocal
from src.db.models import Recipe

recipe_matrix = None
recipe_ids = None
id_to_index = None
recipe_cache = None

def build_feature_vector(recipe: Recipe):
    ingredients_vec = np.array([len(recipe.recipe_ingredients)])
    tags_vec = np.array([len(recipe.tags)])
    kitchens_vec = np.array([len(recipe.kitchens)])
    courses_vec = np.array([len(recipe.courses)])
    nutrition_vec = np.array([
        recipe.kcal or 0,
        recipe.fat or 0,
        recipe.carbs or 0,
        recipe.protein or 0,
        recipe.fibers or 0
    ], dtype=float)
    if np.linalg.norm(nutrition_vec) > 0:
        nutrition_vec /= np.linalg.norm(nutrition_vec)
    vector = np.concatenate([ingredients_vec, tags_vec, kitchens_vec, courses_vec, nutrition_vec])
    return vector

def load_recipe_matrix():
    db = SessionLocal()
    recipes = db.query(Recipe)\
        .options(joinedload(Recipe.recipe_ingredients),
                 joinedload(Recipe.tags),
                 joinedload(Recipe.kitchens),
                 joinedload(Recipe.courses))\
        .all()
    
    vectors = []
    ids = []
    cache = {}

    for r in recipes:
        vec = build_feature_vector(r)
        vectors.append(vec)
        ids.append(r.id)
        cache[r.id] = {
            "id": r.id,
            "title": r.title,
            "kcal": r.kcal,
            "image_link": f"https://placehold.co/600x400?text={r.title.replace(' ', '+')}"
        }

    recipe_matrix = np.vstack(vectors)
    recipe_ids = ids
    id_to_index = {rid: i for i, rid in enumerate(recipe_ids)}
    recipe_cache = cache

    db.close()
    return recipe_matrix, recipe_ids, id_to_index, recipe_cache