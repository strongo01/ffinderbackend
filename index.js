import fs from "fs";
import express from "express";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();
const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;

const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;

const BASE_URL = "https://platform.fatsecret.com/rest/server.api";
const TOKEN_URL = "https://oauth.fatsecret.com/connect/token";

let cachedToken = null;
let tokenExpiry = 0;

const http = axios.create({ timeout: 15000, maxRedirects: 5 });

async function getAccessToken() {
  const now = Date.now();
  if (cachedToken && now < tokenExpiry) return cachedToken;

  const resp = await axios.post(
    TOKEN_URL,
    new URLSearchParams({ grant_type: "client_credentials", scope: "basic" }),
    { auth: { username: CLIENT_ID, password: CLIENT_SECRET } }
  );

  cachedToken = resp.data.access_token;
  tokenExpiry = now + resp.data.expires_in * 1000 - 5000;
  console.log("✅ Access Token verkregen");
  return cachedToken;
}

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
console.log('API Response Data:', JSON.stringify(resp.data, null, 2)); 
return resp.data;
  } catch (err) {
    console.error(`Fout bij ${title}:`, err.response?.data || err.message);
    return { error: err.message };
  }
}

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
    { method: "recipes.search.v3", search_expression: query, format: "json", region: "nl" },
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

app.listen(PORT, () => console.log(`✅ Server running on port ${PORT}`));
