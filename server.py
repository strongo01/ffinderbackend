import os
import json
import sqlite3
import pandas as pd
import numpy as np
from fastapi import FastAPI, Body, HTTPException
from typing import Any, List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager
import random

recipes_df = None
tfidf_matrix = None
raw_json_data = None
manipulated_recipes_data = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global recipes_df, tfidf_matrix, raw_json_data, manipulated_recipes_data
    
    # Load manipulated_recipes_3.json for general operations (search, get_recipe_by_id)
    with open("manipulated_recipes_3.json", "r") as f:
        manipulated_recipes_data = json.load(f)
    
    # Load recipes_for_cbrs.json for recommendations
    with open("recipes_for_cbrs.json", "r") as f:
        raw_json_data = json.load(f)

    flattened_data = []
    for recipe in raw_json_data:
        features = (recipe["features"]["ingredients"] +
                    recipe["features"]["tags"] +
                    recipe["features"]["kitchen"] +
                    recipe["features"]["course"])
        flattened_data.append({"id": recipe["id"], "title": recipe["title"], "content": features})

    recipes_df = pd.DataFrame(flattened_data)
    exploded = recipes_df.explode("content")
    binary_matrix = pd.crosstab(exploded["id"], exploded["content"])
    
    total_recipes = len(recipes_df)
    item_counts = (binary_matrix > 0).sum(axis=0)
    idf = np.log(total_recipes / (item_counts + 1))
    tfidf_matrix = binary_matrix * idf
    
    with sqlite3.connect("ratings.db") as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS ratings ("
                  "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                  "user_id TEXT NOT NULL,"
                  "recipe_id INTEGER NOT NULL,"
                  "rating REAL NOT NULL)")
    yield

app = FastAPI(lifespan=lifespan)

class Rating(BaseModel):
    user_id: str
    recipe_id: int
    rating: float

@app.get("/recipes/search")
async def search_recipes(query: str):
    results = []
    for recipe in manipulated_recipes_data:
        if query.lower() in recipe['title'].lower():
            results.append({
                'id': recipe['id'],
                'title': recipe['title'],
                'image_link': f"https://placehold.co/600x400?text={recipe['title'].replace(' ', '+')}"
            })
    return results

@app.get("/recipes/{recipe_id}")
async def get_recipe_by_id(recipe_id: int):
    recipe = next((r for r in manipulated_recipes_data if r["id"] == recipe_id), None)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    # Add image_link to the recipe
    recipe_with_image = dict(recipe)
    recipe_with_image['image_link'] = f"https://placehold.co/600x400?text={recipe['title'].replace(' ', '+')}"
    return recipe_with_image

@app.post("/recipes/rate")
async def rate_recipe(rating: Rating):
    with sqlite3.connect("ratings.db") as conn:
        conn.execute("INSERT INTO ratings (user_id, recipe_id, rating) VALUES (?, ?, ?)", 
                     (rating.user_id, rating.recipe_id, rating.rating))
    return {"status": "success"}

@app.get("/recipes/get_recommendations/{user_id}")
async def get_recommendations(user_id: str, limit: int = 5):
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT recipe_id, rating FROM ratings WHERE user_id = ?", (user_id,)).fetchall()
        all_ratings = conn.execute("SELECT recipe_id, COUNT(*) as count FROM ratings GROUP BY recipe_id").fetchall()
    
    recipe_popularity = {row["recipe_id"]: row["count"] for row in all_ratings}
    
    if not rows:
        all_recipes = recipes_df['id'].tolist()
        popular_recipes = sorted(all_recipes, key=lambda x: recipe_popularity.get(x, 0), reverse=True)
        
        num_popular = max(1, int(limit * 0.8))
        num_random = limit - num_popular
        
        selected = popular_recipes[:num_popular]
        remaining = [r for r in all_recipes if r not in selected]
        random_selections = random.sample(remaining, min(num_random, len(remaining)))
        selected.extend(random_selections)
        
        results = []
        for recipe_id in selected:
            recipe = next((r for r in manipulated_recipes_data if r["id"] == recipe_id), None)
            if recipe:
                results.append({
                    'id': recipe['id'],
                    'title': recipe['title'],
                    'image_link': f"https://placehold.co/600x400?text={recipe['title'].replace(' ', '+')}"
                })
        return results

    user_ratings_series = pd.Series({row["recipe_id"]: row["rating"] for row in rows})
    rated_recipe_ids = set(user_ratings_series.index)
    
    valid_ids = user_ratings_series.index.intersection(tfidf_matrix.index)
    if valid_ids.empty:
        raise HTTPException(status_code=404, detail="Rated recipes not found in current dataset.")
        
    user_features_matrix = tfidf_matrix.loc[valid_ids]
    user_profile = user_features_matrix.T.dot(user_ratings_series.loc[valid_ids])
    
    scores = (tfidf_matrix.dot(user_profile) / user_profile.sum())
    
    results = recipes_df[['id', 'title']].set_index('id').copy()
    results['score'] = scores
    results['popularity'] = results.index.map(lambda x: recipe_popularity.get(x, 0))
    
    unrated = results[~results.index.isin(rated_recipe_ids)].copy()
    
    num_recommendations = max(1, int(limit * 0.8))
    num_popular = max(0, int(limit * 0.15))
    num_random = limit - num_recommendations - num_popular
    
    recommendation_items = unrated.nlargest(num_recommendations, 'score')
    remaining = unrated[~unrated.index.isin(recommendation_items.index)]
    
    popular_items = remaining.nlargest(num_popular, 'popularity')
    remaining = remaining[~remaining.index.isin(popular_items.index)]
    
    if num_random > 0 and len(remaining) > 0:
        random_items = remaining.sample(n=min(num_random, len(remaining)))
    else:
        random_items = pd.DataFrame()
    
    final_results = pd.concat([recommendation_items, popular_items, random_items])[['id', 'title']]
    
    results_list = []
    for idx, row in final_results.iterrows():
        recipe = next((r for r in manipulated_recipes_data if r["id"] == row['id']), None)
        if recipe:
            results_list.append({
                'id': recipe['id'],
                'title': recipe['title'],
                'image_link': f"https://placehold.co/600x400?text={recipe['title'].replace(' ', '+')}"
            })
    
    return results_list