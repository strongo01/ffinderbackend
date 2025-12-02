import dotenv from "dotenv";
dotenv.config();

import axios from "axios";

const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;

const BASE_URL = "https://platform.fatsecret.com/rest/server.api";
const TOKEN_URL = "https://oauth.fatsecret.com/connect/token";

let cachedToken = null;
let tokenExpiry = 0;

export async function getAccessToken() {
  const now = Date.now();
  if (cachedToken && now < tokenExpiry) return cachedToken;

  const resp = await axios.post(
    TOKEN_URL,
    new URLSearchParams({ grant_type: "client_credentials", scope: "basic" }),
    { auth: { username: CLIENT_ID, password: CLIENT_SECRET } }
  );

  cachedToken = resp.data.access_token;
  tokenExpiry = now + resp.data.expires_in * 1000 - 5000;
  return cachedToken;
}

export async function callFatSecret(params, title = "") {
  try {
    const token = await getAccessToken();
    const resp = await axios.get(BASE_URL, {
      headers: { Authorization: `Bearer ${token}` },
      params
    });

    return resp.data;
  } catch (err) {
    return { error: err.response?.data || err.message };
  }
}

export async function callOpenFoodFacts(barcode) {
  try {
    const url = `https://world.openfoodfacts.org/api/v0/product/${barcode}.json`;
    const resp = await axios.get(url);

    return resp.data.product || {};
  } catch (err) {
    return { error: err.message };
  }
}
