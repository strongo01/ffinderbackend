import express from "express";
import fetch from "node-fetch";
import Database from "better-sqlite3";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json());

const recipeImagesDir = process.env.RECIPE_IMAGES_DIR || "/home/triskattie/fatsecret/recipe_images_api";
app.use("/recipe-images", express.static(recipeImagesDir, {
  maxAge: "30d",
  immutable: true,
  fallthrough: false,
}));

// Auth Middleware
app.use((req, res, next) => {
  const appKey = req.headers["x-app-key"];
  if (!appKey || appKey !== process.env.APP_KEY) {
    return res.status(401).json({ error: "Ongeldige of ontbrekende API key" });
  }
  next();
});

const productDbPath = process.env.PRODUCT_DB_PATH || "./products.db";
const productDb = new Database(productDbPath, { readonly: true, fileMustExist: true });
productDb.pragma("query_only = ON");
const productByBarcode = productDb.prepare("SELECT * FROM products WHERE barcode = ?");
function searchProducts(query) {
  const terms = query.trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  const clauses = terms.map(() => "(lower(coalesce(product_name, '')) LIKE ? OR lower(coalesce(generic_name, '')) LIKE ? OR lower(coalesce(brands, '')) LIKE ?)").join(" OR ");
  const values = terms.flatMap((term) => {
    const pattern = `%${term.toLowerCase()}%`;
    return [pattern, pattern, pattern];
  });
  return productDb.prepare(`SELECT * FROM products WHERE ${clauses} LIMIT 50`).all(...values);
}

// --- Helper Functions ---
function isBarcode(str) {
  return /^[0-9]{8,14}$/.test(str);
}

function formatProduct(p) {
  if (!p) return null;
  const n = p;
  const imageUrl = p.image_url || null;
  const servingSize = p.serving_size || null;

  return {
    barcode: p.barcode || null,
    product_name: p.product_name || null,
    brands: p.brands || null,
    nutriscore: p.nutriscore || null,
    serving_size: servingSize,
    nutriments: {
      energy_kcal: n.energy_kcal ?? null,
      fat: n.fat ?? null,
      saturated_fat: n.saturated_fat ?? null,
      carbohydrates: n.carbohydrates ?? null,
      sugars: n.sugars ?? null,
      fiber: n.fiber ?? null,
      proteins: n.proteins ?? null,
      salt: n.salt ?? null,
    },
    ingredients: p.ingredients || null,
    vegan: Boolean(p.vegan),
    vegetarian: Boolean(p.vegetarian),
    image_url: imageUrl,
  };
}

// --- Product Routes ---
app.get("/product", async (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).json({ error: "q ontbreekt" });
  let results = [];
  if (isBarcode(query)) {
    const p = productByBarcode.get(query);
    if (p) results.push(formatProduct(p));
  } else {
    results = searchProducts(query).map(formatProduct);
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