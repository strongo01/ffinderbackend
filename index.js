// index.js
import fs from "fs";
import express from "express";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();
const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;

// 🔹 FatSecret OAuth2 credentials
const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;
const BASE_URL = "https://platform.fatsecret.com/rest/server.api";
const TOKEN_URL = "https://oauth.fatsecret.com/connect/token";

let cachedToken = null;
let tokenExpiry = 0;

// Utility: small axios instance with timeout
const http = axios.create({ timeout: 15000, maxRedirects: 5 });

// 🔹 Access token ophalen en cachen
async function getAccessToken() {
  const now = Date.now();
  if (cachedToken && now < tokenExpiry) return cachedToken;

  const resp = await axios.post(
    TOKEN_URL,
    new URLSearchParams({ grant_type: "client_credentials", scope: "basic" }),
    { auth: { username: CLIENT_ID, password: CLIENT_SECRET } }
  );

  cachedToken = resp.data.access_token;
  tokenExpiry = now + resp.data.expires_in * 1000 - 5000; // 5 sec marge
  console.log("✅ Access Token verkregen");
  return cachedToken;
}

// 🔹 Functie om FatSecret API aan te roepen
async function callFatSecret(params, title) {
  try {
    const token = await getAccessToken();
    const resp = await axios.get(BASE_URL, {
      headers: { Authorization: `Bearer ${token}` },
      params,
    });

    console.log(`\n🔹 ${title}`);
    console.log(`Methode: ${params.method}`);
    console.log(`Status: ${resp.status}`);
    return resp.data;
  } catch (err) {
    console.error(`Fout bij ${title}:`, err.response?.data || err.message);
    return { error: err.message };
  }
}

// 🔹 OpenFoodFacts lookup met alleen relevante info
async function callOpenFoodFacts(barcode) {
  try {
    const url = `https://world.openfoodfacts.org/api/v0/product/${barcode}.json`;
    const resp = await axios.get(url);
    const product = resp.data.product || {};

    console.log(`\n🔹 Barcode lookup: ${barcode}`);
    console.log(`Naam: ${product.product_name || "Onbekend"}`);
    console.log(`Merk: ${product.brands || "Onbekend"}`);
    console.log(`Inhoud: ${product.quantity || "Onbekend"}`);

    const nutriments = product.nutriments || {};
    console.log(`Calorieën: ${nutriments["energy-kcal_100g"] ?? "Onbekend"} kcal/100g`);
    console.log(`Eiwit: ${nutriments["proteins_100g"] ?? "Onbekend"} g/100g`);
    console.log(`Vet: ${nutriments["fat_100g"] ?? "Onbekend"} g/100g`);
    console.log(`Koolhydraten: ${nutriments["carbohydrates_100g"] ?? "Onbekend"} g/100g`);

    if (product.image_front_url) console.log(`Afbeelding: ${product.image_front_url}`);
    return product;
  } catch (err) {
    console.error(`Fout bij OpenFoodFacts:`, err.response?.data || err.message);
    return { error: err.message };
  }
}

// 🔹 FatSecret Image Recognition
async function classifyFood(imageUrlOrPath) {
  try {
    let base64;

    if (/^https?:\/\//i.test(imageUrlOrPath)) {
      // Download image van URL
      const resp = await axios.get(imageUrlOrPath, { responseType: "arraybuffer" });
      base64 = Buffer.from(resp.data, "binary").toString("base64");
    } else {
      // Lokale afbeelding
      if (!fs.existsSync(imageUrlOrPath)) throw new Error("Lokale afbeelding niet gevonden: " + imageUrlOrPath);
      base64 = fs.readFileSync(imageUrlOrPath, { encoding: "base64" });
    }

    // FatSecret API aanroepen
    const token = await getAccessToken();
    const resp = await axios.post(
      "https://platform.fatsecret.com/rest/image-recognition/v2",
      {
        image_b64: base64,
        region: "NL",         // of "US", "FR", etc.
        language: "nl",
        include_food_data: true,
        eaten_foods: []       // Optioneel: array van eerder gegeten voedingsmiddelen
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        }
      }
    );

    // Resultaten loggen
    const data = resp.data;
    if (data && data.foods && data.foods.length > 0) {
      data.foods.forEach(food => {
        console.log(`🍽 ${food.food_name} - ${food.serving_description || ""}`);
        if (food.nutritional_info) {
          console.log(`   Calories: ${food.nutritional_info.calories || "Onbekend"} kcal`);
          console.log(`   Proteins: ${food.nutritional_info.protein || "Onbekend"} g`);
          console.log(`   Fat: ${food.nutritional_info.fat || "Onbekend"} g`);
          console.log(`   Carbs: ${food.nutritional_info.carbohydrates || "Onbekend"} g`);
        }
      });
    } else {
      console.log("Geen voedsel herkend in afbeelding");
    }

    return data;

  } catch (err) {
    console.error("Fout bij FatSecret Image Recognition:", err.response?.data || err.message);
    return { error: err.message, details: err.response?.data };
  }
}


// 🔹 Express routes (proxy endpoints)
app.get("/search", async (req, res) => {
  const { query } = req.query;
  if (!query) return res.status(400).json({ error: "query param ontbreekt" });
  const data = await callFatSecret(
    { method: "foods.search", search_expression: query, format: "json", region: "nl" },
    `Zoeken op naam: ${query}`
  );
  res.json(data);
});

app.get("/recipe", async (req, res) => {
  const { query } = req.query;
  if (!query) return res.status(400).json({ error: "query param ontbreekt" });
  const data = await callFatSecret(
    { method: "recipes.search.v2", search_expression: query, format: "json", region: "nl" },
    `Zoeken naar recepten: ${query}`
  );
  res.json(data);
});

app.get("/barcode", async (req, res) => {
  const { code } = req.query;
  if (!code) return res.status(400).json({ error: "code param ontbreekt" });
  const data = await callOpenFoodFacts(code);
  res.json(data);
});

app.get("/image", async (req, res) => {
  const { imageurl } = req.query;
  if (!imageurl) return res.status(400).json({ error: "imageurl param ontbreekt" });

  const data = await classifyFood(imageurl);
  res.json(data);
});


// 🔹 Server starten
app.listen(PORT, () => console.log(`✅ Server running on port ${PORT}`));
