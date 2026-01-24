import express from "express";
import fetch from "node-fetch";
import { MongoClient } from "mongodb";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json());

// Auth Middleware
app.use((req, res, next) => {
  const appKey = req.headers["x-app-key"];
  if (!appKey || appKey !== process.env.APP_KEY) {
    return res.status(401).json({ error: "Ongeldige of ontbrekende API key" });
  }
  next();
});

const uri = process.env.MONGO_URI;
const client = new MongoClient(uri);
await client.connect();
const db = client.db("off_db");
const products = db.collection("products");

// --- Helper Functions ---
function isBarcode(str) {
  return /^[0-9]{8,14}$/.test(str);
}

function formatProduct(p) {
  if (!p) return null;
  const n = p.nutriments || {};
  const tags = Array.isArray(p.ingredients_analysis_tags) ? p.ingredients_analysis_tags : [];
  const imageUrl = p.image_url || p.image_front_url || p.selected_images?.front?.display?.en || p.image_front_small_url || p.image_small_url || null;
  const servingSize = p.serving_size || p.serving_size_with_unit || p.serving_quantity || null;

  return {
    barcode: p.code || null,
    product_name: p.product_name || null,
    brands: p.brands || p.brand || null,
    nutriscore: p.nutriscore_grade || null,
    serving_size: servingSize,
    nutriments: {
      energy_kcal: n["energy-kcal_100g"] ?? null,
      fat: n.fat_100g ?? null,
      saturated_fat: n["saturated-fat_100g"] ?? null,
      carbohydrates: n.carbohydrates_100g ?? null,
      sugars: n.sugars_100g ?? null,
      fiber: n.fiber_100g ?? null,
      proteins: n.proteins_100g ?? null,
      salt: n.salt_100g ?? null,
    },
    ingredients: p.ingredients_text || null,
    vegan: tags.includes("en:vegan"),
    vegetarian: tags.includes("en:vegetarian"),
    image_url: imageUrl,
  };
}

// --- Product Routes ---
app.get("/product", async (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).json({ error: "q ontbreekt" });
  let results = [];
  if (isBarcode(query)) {
    const p = await products.findOne({ code: query });
    if (p) results.push(formatProduct(p));
  } else {
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(escapedQuery.split(" ").join("|"), "i");
    const cursor = products.find({ $or: [{ product_name: regex }, { generic_name: regex }, { brands: regex }] }).limit(50);
    results = (await cursor.toArray()).map(formatProduct);
  }
  res.json({ foods: { food: results } });
});

// --- Recipe Routes ---
const PYTHON_SERVER_URL = process.env.PYTHON_SERVER_URL;

/**
 * NEW: Get unique filters (kitchens, courses, tags) 
 * This helps your frontend build the filter UI dynamically.
 */
app.get("/recipes/filters", async (req, res) => {
  try {
    const response = await fetch(`${PYTHON_SERVER_URL}/recipes/filters`);
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch recipe filters" });
  }
});

/**
 * UPDATED: Forward all search/filter params to Python
 */
app.get("/recipes/search", async (req, res) => {
  try {
    // We convert the req.query object into a URL search string
    // This forwards query, kitchen, max_kcal, etc. automatically
    const queryParams = new URLSearchParams(req.query).toString();
    
    const response = await fetch(`${PYTHON_SERVER_URL}/recipes/search?${queryParams}`);
    
    if (!response.ok) {
        return res.status(response.status).json({ error: "Python search error" });
    }

    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Recipe search failed" });
  }
});

app.get("/recipes/get/:recipeId", async (req, res) => {
  try {
    const { recipeId } = req.params;
    const response = await fetch(`${PYTHON_SERVER_URL}/recipes/get/${recipeId}`);
    if (!response.ok) return res.status(response.status).json({ error: "Recipe not found" });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch recipe" });
  }
});

app.post("/recipes/rate", async (req, res) => {
  try {
    const { user_id, recipe_id, rating } = req.body;
    if (!user_id || !recipe_id || rating === undefined) {
      return res.status(400).json({ error: "user_id, recipe_id, and rating are required" });
    }
    const response = await fetch(`${PYTHON_SERVER_URL}/recipes/rate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id, recipe_id, rating }),
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to rate recipe" });
  }
});

app.get("/recipes/recommendations/:userId", async (req, res) => {
  try {
    const { userId } = req.params;
    const { limit = 5 } = req.query;
    const response = await fetch(`${PYTHON_SERVER_URL}/recipes/get_recommendations/${userId}?limit=${limit}`);
    if (!response.ok) return res.status(response.status).json({ error: "Failed to get recommendations" });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch recommendations" });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 Server running on port ${PORT}`);
});