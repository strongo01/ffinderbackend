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
let tokenExpiry = {};
let cachedTokens = {};

// Utility: small axios instance with timeout
const http = axios.create({ timeout: 15000, maxRedirects: 5 });

// 🔹 Access token ophalen en cachen
async function getAccessToken(scope = "basic") {
  const now = Date.now();

  if (cachedTokens[scope] && now < tokenExpiry[scope]) {
    return cachedTokens[scope];
  }

  const resp = await axios.post(
    TOKEN_URL,
    new URLSearchParams({
      grant_type: "client_credentials",
      scope: scope
    }),
    { auth: { username: CLIENT_ID, password: CLIENT_SECRET } }
  );

  cachedTokens[scope] = resp.data.access_token;
  tokenExpiry[scope] = now + resp.data.expires_in * 1000 - 5000;
  console.log(`✅ Access Token verkregen voor scope: ${scope}`);
  return cachedTokens[scope];
}

// 🔹 Functie om FatSecret API aan te roepen
async function callFatSecret(params, title) {
  try {
    const token = await getAccessToken("basic");
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
// 🔹 FatSecret Image Recognition (robust download + diagnostics)
async function classifyFood(imageUrlOrPath) {
  try {
    let base64;

    if (/^https?:\/\//i.test(imageUrlOrPath)) {
      // Candidate URLs: original and encoded (handles spaces / weird chars)
      const candidates = [imageUrlOrPath, encodeURI(imageUrlOrPath)];
      let buf = null;
      let lastErr = null;

      // Browser-like headers to avoid hotlink blocking
      const headers = {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        Accept: "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
      };

      for (const candidate of candidates) {
        try {
          const resp = await http.get(candidate, {
            responseType: "arraybuffer",
            headers: { ...headers, Referer: candidate },
            maxRedirects: 5,
            // increase max body size if needed
            maxContentLength: 50 * 1024 * 1024,
            validateStatus: status => status >= 200 && status < 400, // accept 3xx (axios will handle redirects)
          });

          console.log("→ download status:", resp.status);
          console.log("→ content-type:", resp.headers["content-type"]);

          if (!resp.data || resp.data.length === 0) {
            lastErr = new Error("Lege response body");
            console.warn("Waarschuwing: lege body voor", candidate);
            continue;
          }

          buf = Buffer.from(resp.data, "binary");
          break;
        } catch (err) {
          lastErr = err;
          console.warn(`Download poging mislukt voor ${candidate}:`, err.message);
          if (err.response) {
            console.warn("Response status:", err.response.status);
          }
          // probeer volgende candidate
        }
      }

      if (!buf) {
        // gedetailleerde fout teruggeven voor debugging
        const message = lastErr?.response?.status
          ? `Image download failed with status ${lastErr.response.status}`
          : `Image download failed: ${lastErr?.message || "unknown"}`;
        throw new Error(message);
      }

      // Optioneel: check minimale grootte
      if (buf.length < 1000) {
        console.warn("Waarschuwing: gedownloade afbeelding is erg klein:", buf.length, "bytes");
      }

      base64 = buf.toString("base64");
      console.log("📸 Base64 length:", base64.length);
    } else {
      // Lokale afbeelding
      if (!fs.existsSync(imageUrlOrPath)) throw new Error("Lokale afbeelding niet gevonden: " + imageUrlOrPath);
      base64 = fs.readFileSync(imageUrlOrPath, { encoding: "base64" });
      console.log("📸 Base64 length (local):", base64.length);
    }

    // Basic sanity check
    if (!base64 || base64.length === 0) throw new Error("Base64 image is empty after download");

    // FatSecret API aanroepen (zorg dat token scope 'image-recognition' heeft)
    // Correct voor image recognition
    const token = await getAccessToken("premier");
    const resp = await axios.post(
      "https://platform.fatsecret.com/rest/image-recognition/v2",
      {
        image_b64: base64,
        region: "NL",         // of "US", "FR", etc.
        language: "nl",
        include_food_data: true,
        eaten_foods: []
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        timeout: 30000
      }
    );

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
    // show deeper debug info when axios gave a Buffer or empty body
    const details = err.response?.data ?? err.message;
    console.error("Fout bij FatSecret Image Recognition:", details);
    return { error: err.message, details: err.response?.data ?? null };
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
