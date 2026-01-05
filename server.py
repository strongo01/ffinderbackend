import os
import json
import sqlite3
import pandas as pd
import numpy as np
from fastapi import FastAPI, Body, HTTPException
from typing import Any, List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager

recipes_df = None
tfidf_matrix = None
raw_json_data = None  

@asynccontextmanager
async def lifespan(app: FastAPI):
    global recipes_df, tfidf_matrix, raw_json_data
    
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
    results = recipes_df[recipes_df['title'].str.contains(query, case=False, na=False)]
    return results[['id', 'title']].to_dict(orient="records")

@app.get("/recipes/{recipe_id}")
async def get_recipe_by_id(recipe_id: int):
    recipe = next((r for r in raw_json_data if r["id"] == recipe_id), None)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe

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
    
    if not rows:
        raise HTTPException(status_code=404, detail="No ratings found for this user. Rate some recipes first!")

    user_ratings_series = pd.Series({row["recipe_id"]: row["rating"] for row in rows})
    
    valid_ids = user_ratings_series.index.intersection(tfidf_matrix.index)
    if valid_ids.empty:
        raise HTTPException(status_code=404, detail="Rated recipes not found in current dataset.")
        
    user_features_matrix = tfidf_matrix.loc[valid_ids]
    user_profile = user_features_matrix.T.dot(user_ratings_series.loc[valid_ids])
    
    scores = (tfidf_matrix.dot(user_profile) / user_profile.sum())
    
    results = recipes_df[['id', 'title']].set_index('id')
    results['score'] = scores
    
    recommendations = results.drop(index=valid_ids)
    top_items = recommendations.sort_values(by="score", ascending=False).head(limit)
    
    return top_items.reset_index().to_dict(orient="records")