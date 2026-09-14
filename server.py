import os
import json
import sqlite3
import random
import logging
import time
import math
from collections import Counter, defaultdict

from fastapi import FastAPI, Body, HTTPException, Request
from typing import Any, List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager

recipes_df = None
raw_json_data = None
manipulated_recipes_data = None
recipe_ids = []
recipe_titles = {}
recipe_features = {}
feature_postings = defaultdict(list)
feature_idf = {}

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://ffinder.nl").rstrip("/")


def recipe_image_url(recipe_id: int) -> str:
    return f"{PUBLIC_BASE_URL}/recipe-images/{recipe_id}.jpg"


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
    global recipes_df, raw_json_data, manipulated_recipes_data
    global recipe_ids, recipe_titles, recipe_features, feature_postings, feature_idf

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

    recipe_ids = []
    recipe_titles = {}
    recipe_features = {}
    feature_postings = defaultdict(list)
    feature_document_counts = Counter()

    for recipe in raw_json_data:
        rid = recipe["id"]
        features = (recipe["features"]["ingredients"] +
                    recipe["features"]["tags"] +
                    recipe["features"]["kitchen"] +
                    recipe["features"]["course"])
        counts = Counter(features)
        recipe_ids.append(rid)
        recipe_titles[rid] = recipe["title"]
        recipe_features[rid] = counts
        for feature in counts:
            feature_document_counts[feature] += 1

    total_recipes = len(recipe_ids)
    for feature, count in feature_document_counts.items():
        feature_idf[feature] = math.log(total_recipes / (count + 1))
    for rid, counts in recipe_features.items():
        for feature, frequency in counts.items():
            feature_postings[feature].append((rid, frequency * feature_idf[feature]))

    # Keep only compact recipe metadata; scoring uses the sparse postings above.
    recipes_df = None
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
        
        results.append({
            'id': row['id'],
            'title': original_title,
            'image_link': recipe_image_url(row['id'])
        })

    return results

@app.get("/recipes/filters")
async def get_filters():
    kitchens = set()
    courses = set()
    tags = set()

    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT data FROM recipes").fetchall()

    for row in rows:
        try:
            recipe = json.loads(row["data"])
        except Exception:
            continue

        for k in recipe.get("kitchens", []):
            if k.get("name"):
                kitchens.add(k["name"])

        for c in recipe.get("courses", []):
            if c.get("main"):
                courses.add(c["main"])

        for t in recipe.get("tags", []):
            if t.get("sub"):
                tags.add(t["sub"])

    return {
        "kitchens": sorted(kitchens),
        "courses": sorted(courses),
        "tags": sorted(tags),
        "difficulties": ["eenvoudig", "gemiddeld", "uitdagend"],
        "max_kcal": 1500,
        "max_prep_time": 120
    }


@app.get("/recipes/get/{recipe_id}")
async def get_recipe_by_id(recipe_id: int):
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT data FROM recipes WHERE id = ?", (recipe_id,)).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe = json.loads(row['data'])
    recipe_with_image = dict(recipe)
    recipe_with_image['image_link'] = recipe_image_url(recipe_id)
    return recipe_with_image

@app.post("/recipes/rate")
async def rate_recipe(rating: Rating):
    with sqlite3.connect("ratings.db") as conn:
        conn.execute("INSERT INTO ratings (user_id, recipe_id, rating) VALUES (?, ?, ?)", 
                     (rating.user_id, rating.recipe_id, rating.rating))
    return {"status": "success"}

def _recipe_results(selected_ids):
    if not selected_ids:
        return []
    placeholders = ",".join("?" for _ in selected_ids)
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT id, data FROM recipes WHERE id IN ({placeholders})", selected_ids).fetchall()
    by_id = {row["id"]: row["data"] for row in rows}
    results = []
    for recipe_id in selected_ids:
        data = by_id.get(recipe_id)
        if not data:
            continue
        try:
            recipe = json.loads(data)
        except Exception:
            recipe = {"id": recipe_id}
        recipe["image_link"] = recipe_image_url(recipe_id)
        results.append(recipe)
    return results


def _fallback_recommendations(recipe_popularity, limit):
    popular = sorted(recipe_ids, key=lambda rid: recipe_popularity.get(rid, 0), reverse=True)
    num_popular = max(1, int(limit * 0.8))
    selected = popular[:num_popular]
    remaining = [rid for rid in recipe_ids if rid not in set(selected)]
    selected.extend(random.sample(remaining, min(limit - len(selected), len(remaining))))
    return _recipe_results(selected[:limit])


@app.get("/recipes/get_recommendations/{user_id}")
async def get_recommendations(user_id: str, limit: int = 5):
    with sqlite3.connect("ratings.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT recipe_id, rating FROM ratings WHERE user_id = ?", (user_id,)).fetchall()
        all_ratings = conn.execute("SELECT recipe_id, COUNT(*) as count FROM ratings GROUP BY recipe_id").fetchall()

    recipe_popularity = {row["recipe_id"]: row["count"] for row in all_ratings}
    if not rows:
        return _fallback_recommendations(recipe_popularity, limit)

    user_ratings = {row["recipe_id"]: row["rating"] for row in rows}
    valid_ratings = {rid: rating for rid, rating in user_ratings.items() if rid in recipe_features}
    if not valid_ratings:
        return _fallback_recommendations(recipe_popularity, limit)

    user_profile = defaultdict(float)
    for recipe_id, rating in valid_ratings.items():
        for feature, frequency in recipe_features[recipe_id].items():
            user_profile[feature] += frequency * feature_idf[feature] * rating

    profile_weight = sum(user_profile.values())
    if not profile_weight:
        return _fallback_recommendations(recipe_popularity, limit)

    scores = defaultdict(float)
    for feature, profile_value in user_profile.items():
        for recipe_id, feature_weight in feature_postings[feature]:
            scores[recipe_id] += feature_weight * profile_value

    rated_ids = set(user_ratings)
    unrated_ids = [rid for rid in recipe_ids if rid not in rated_ids]
    num_recommendations = max(1, int(limit * 0.8))
    num_popular = max(0, int(limit * 0.15))
    num_random = limit - num_recommendations - num_popular

    recommendation_ids = sorted(unrated_ids, key=lambda rid: scores.get(rid, 0), reverse=True)[:num_recommendations]
    remaining = [rid for rid in unrated_ids if rid not in set(recommendation_ids)]
    popular_ids = sorted(remaining, key=lambda rid: recipe_popularity.get(rid, 0), reverse=True)[:num_popular]
    remaining = [rid for rid in remaining if rid not in set(popular_ids)]
    random_ids = random.sample(remaining, min(num_random, len(remaining))) if num_random > 0 else []

    selected = recommendation_ids + popular_ids + random_ids
    if len(selected) < limit:
        selected_set = set(selected)
        selected.extend(rid for rid in sorted(unrated_ids, key=lambda x: recipe_popularity.get(x, 0), reverse=True) if rid not in selected_set)
        selected = selected[:limit]
    return _recipe_results(selected)
