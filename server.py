import os
import json
import sqlite3
import pandas as pd
import numpy as np
from fastapi import FastAPI, Body, HTTPException, Request
from typing import Any, List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager
import random
import logging 
import time

recipes_df = None
tfidf_matrix = None
raw_json_data = None
manipulated_recipes_data = None

os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("request")
file_handler = logging.FileHandler("logs/app.log")
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
logger.propagate = False




@asynccontextmanager
async def lifespan(app: FastAPI):
    global recipes_df, tfidf_matrix, raw_json_data, manipulated_recipes_data

    # Ensure ratings table exists
    with sqlite3.connect("ratings.db") as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS ratings ("
                     "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                     "user_id TEXT NOT NULL,"
                     "recipe_id INTEGER NOT NULL,"
                     "rating REAL NOT NULL)")

        # Create recipes table to store manipulated recipes if it doesn't exist
        conn.execute("CREATE TABLE IF NOT EXISTS recipes (id INTEGER PRIMARY KEY, title TEXT, data TEXT)")

        # If recipes table is empty, import from the JSON file once
        cur = conn.execute("SELECT COUNT(1) as cnt FROM recipes")
        row = cur.fetchone()
        need_import = (row is None) or (row[0] == 0)

        if need_import:
            # Stream insert to avoid keeping the whole file in memory
            with open("manipulated_recipes_3.json", "r", encoding="utf-8") as f:
                items = json.load(f)
                to_insert = []
                for r in items:
                    rid = r.get("id")
                    title = r.get("title", "")
                    data_text = json.dumps(r, ensure_ascii=False)
                    to_insert.append((rid, title, data_text))
                    if len(to_insert) >= 500:
                        conn.executemany("INSERT OR REPLACE INTO recipes (id, title, data) VALUES (?, ?, ?)", to_insert)
                        conn.commit()
                        to_insert = []
                if to_insert:
                    conn.executemany("INSERT OR REPLACE INTO recipes (id, title, data) VALUES (?, ?, ?)", to_insert)
                    conn.commit()

    # Load recipes_for_cbrs.json for recommendations (kept in memory for TF-IDF)
    with open("recipes_for_cbrs.json", "r", encoding="utf-8") as f:
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

    # Avoid keeping manipulated_recipes in memory
    manipulated_recipes_data = None
    yield

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        raise
    process_time = time.time() - start_time

    logger.info(
        "%s %s - %s - %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )
    return response

class Rating(BaseModel):
    user_id: str
    recipe_id: int
    rating: float

@app.get("/recipes/search")
async def search_recipes(
    query: Optional[str] = None,
    kitchen: Optional[str] = None,
    course: Optional[str] = None,
    difficulty: Optional[str] = None,
    max_prep: Optional[int] = None,
    max_kcal: Optional[int] = None,
    min_protein: Optional[int] = None,
    tag: Optional[str] = None
):
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        sql = "SELECT id, title FROM recipes WHERE 1=1"
        params = []

        if query:
            sql += " AND (title LIKE ? OR title LIKE ? OR title LIKE ? OR title = ?)"
            params.extend([f"{query} %", f"% {query}", f"% {query} %", query])

        if kitchen:
            sql += " AND json_extract(data, '$.kitchens[0].name') = ?"
            params.append(kitchen)
        
        if course:
            sql += " AND json_extract(data, '$.courses[0].main') = ?"
            params.append(course)

        if difficulty:
            sql += " AND json_extract(data, '$.difficulty.name') = ?"
            params.append(difficulty)

        if max_prep:
            sql += " AND CAST(json_extract(data, '$.preparation_time') AS INTEGER) <= ?"
            params.append(max_prep)

        if max_kcal:
            sql += " AND CAST(json_extract(data, '$.kcal') AS INTEGER) <= ?"
            params.append(max_kcal)

        if min_protein:
            sql += " AND CAST(json_extract(data, '$.protein') AS INTEGER) >= ?"
            params.append(min_protein)

        if tag:
            sql += " AND data LIKE ?"
            params.append(f'%"{tag}"%')

        sql += " COLLATE NOCASE LIMIT 100"
        
        cur.execute(sql, params)
        rows = cur.fetchall()

    results = []
    for row in rows:
        original_title = row["title"] or ""
        url_title = original_title.replace(" ", "-")
        
        results.append({
            'id': row['id'],
            'title': original_title,
            'image_link': f"https://boodschappen.nl/app/uploads/recipe_images/4by3_header@2x/{url_title.lower()}.jpg"
        })

    return results

@app.get("/recipes/{recipe_id}")
async def get_recipe_by_id(recipe_id: int):
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT data FROM recipes WHERE id = ?", (recipe_id,)).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe = json.loads(row['data'])
    recipe_with_image = dict(recipe)
    title = recipe.get('title', '')
    recipe_with_image['image_link'] = f"https://placehold.co/600x400?text={title.replace(' ', '+')}"
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
        with sqlite3.connect("ratings.db") as conn:
            conn.row_factory = sqlite3.Row
            for recipe_id in selected:
                row = conn.execute("SELECT data FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
                if row and row['data']:
                    try:
                        recipe = json.loads(row['data'])
                    except Exception:
                        recipe = {"id": recipe_id}
                    title = recipe.get('title', '')
                    recipe_with_image = dict(recipe)
                    recipe_with_image['image_link'] = f"https://placehold.co/600x400?text={title.replace(' ', '+')}"
                    results.append(recipe_with_image)
        return results

    user_ratings_series = pd.Series({row["recipe_id"]: row["rating"] for row in rows})
    rated_recipe_ids = set(user_ratings_series.index)
    
    valid_ids = user_ratings_series.index.intersection(tfidf_matrix.index)
    # If no valid rated recipes exist in the CBRS dataset, fall back to popularity-based recommendations
    if valid_ids.empty:
        all_recipes = recipes_df['id'].tolist()
        popular_recipes = sorted(all_recipes, key=lambda x: recipe_popularity.get(x, 0), reverse=True)
        
        num_popular = max(1, int(limit * 0.8))
        num_random = limit - num_popular
        
        selected = popular_recipes[:num_popular]
        remaining = [r for r in all_recipes if r not in selected]
        random_selections = random.sample(remaining, min(num_random, len(remaining)))
        selected.extend(random_selections)
        
        results = []
        with sqlite3.connect("ratings.db") as conn:
            conn.row_factory = sqlite3.Row
            for recipe_id in selected:
                row = conn.execute("SELECT data FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
                if row and row['data']:
                    try:
                        recipe = json.loads(row['data'])
                    except Exception:
                        recipe = {"id": recipe_id}
                    title = recipe.get('title', '')
                    recipe_with_image = dict(recipe)
                    recipe_with_image['image_link'] = f"https://placehold.co/600x400?text={title.replace(' ', '+')}"
                    results.append(recipe_with_image)
        return results
        
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
    
    if len(unrated) == 0:
        all_recipes = recipes_df['id'].tolist()
        popular_recipes = sorted(all_recipes, key=lambda x: recipe_popularity.get(x, 0), reverse=True)
        selected = popular_recipes[:limit]
        
        results_list = []
        with sqlite3.connect("ratings.db") as conn:
            conn.row_factory = sqlite3.Row
            for recipe_id in selected:
                row = conn.execute("SELECT data FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
                if row and row['data']:
                    try:
                        recipe = json.loads(row['data'])
                    except Exception:
                        recipe = {"id": recipe_id}
                    title = recipe.get('title', '')
                    recipe_with_image = dict(recipe)
                    recipe_with_image['image_link'] = f"https://placehold.co/600x400?text={title.replace(' ', '+')}"
                    results_list.append(recipe_with_image)
        return results_list
    
    recommendation_items = unrated.nlargest(num_recommendations, 'score')
    remaining = unrated[~unrated.index.isin(recommendation_items.index)]
    
    popular_items = remaining.nlargest(num_popular, 'popularity')
    remaining = remaining[~remaining.index.isin(popular_items.index)]
    
    if num_random > 0 and len(remaining) > 0:
        random_items = remaining.sample(n=min(num_random, len(remaining)))
    else:
        random_items = pd.DataFrame()
    
    candidates = pd.concat([recommendation_items, popular_items, random_items])
    if len(candidates) < limit and len(unrated) > len(candidates):
        already_selected = set(candidates.index)
        unfilled = unrated[~unrated.index.isin(already_selected)].nlargest(limit - len(candidates), 'popularity')
        candidates = pd.concat([candidates, unfilled])
    
    final_results = candidates.reset_index()[['id', 'title']].head(limit)
    
    results_list = []
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        for idx, row in final_results.iterrows():
            rid = row['id'] if 'id' in row else idx
            db_row = conn.execute("SELECT data FROM recipes WHERE id = ?", (rid,)).fetchone()
            if db_row and db_row['data']:
                try:
                    recipe = json.loads(db_row['data'])
                except Exception:
                    recipe = {"id": rid}
                title = recipe.get('title', '')
                recipe_with_image = dict(recipe)
                recipe_with_image['image_link'] = f"https://placehold.co/600x400?text={title.replace(' ', '+')}"
                results_list.append(recipe_with_image)
    
    return results_list

@app.get("/recipes/filters")
async def get_filters():
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        kitchens = cur.execute("SELECT DISTINCT name FROM kitchens").fetchall()
        courses = cur.execute("SELECT DISTINCT main FROM courses").fetchall()
        tags = cur.execute("SELECT DISTINCT sub FROM tags WHERE sub IS NOT NULL").fetchall()
        
    return {
        "kitchens": [k["name"] for k in kitchens],
        "courses": [c["main"] for c in courses],
        "tags": [t["sub"] for t in tags],
        "difficulties": ["makkelijk", "gemiddeld", "moeilijk"],
        "max_kcal": 1500,
        "max_prep_time": 120
    }