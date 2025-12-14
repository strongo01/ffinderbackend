import express from "express";
import { MongoClient } from "mongodb";
import dotenv from "dotenv";

dotenv.config();

const uri = process.env.MONGO_URI;
const client = new MongoClient(uri);

await client.connect();
const db = client.db("off_db");
const products = db.collection("products");

const app = express();
app.use(express.json());

app.use((req, res, next) => {
  const appKey = req.headers["x-app-key"];
  if (!appKey || appKey !== process.env.APP_KEY) {
    return res.status(401).json({ error: "Ongeldige of ontbrekende API key" });
  }
  next();
});


// Barcode herkenning
function isBarcode(str) {
  return /^[0-9]{8,14}$/.test(str);
}

// Product formatter
function formatProduct(p) {
  if (!p) return null;
  const n = p.nutriments || {};
  const tags = Array.isArray(p.ingredients_analysis_tags) ? p.ingredients_analysis_tags : [];
  const imageUrl =
    p.image_url ||
    p.image_front_url ||
    p.selected_images?.front?.display?.en ||
    p.image_front_small_url ||
    p.image_small_url ||
    null;

  const servingSize =
    p.serving_size ||
    p.serving_size_with_unit ||
    p.serving_quantity ||
    null;

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

// Unified endpoint
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

    const cursor = products
      .find({ $or: [{ product_name: regex }, { generic_name: regex }, { brands: regex }] })
      .limit(50);

    results = (await cursor.toArray()).map(formatProduct);
  }

  // Wrap in foods.food zodat Flutter werkt
  res.json({ foods: { food: results } });
});


app.listen(3000, "0.0.0.0", () => console.log("🚀 Server running on port 3000"));
