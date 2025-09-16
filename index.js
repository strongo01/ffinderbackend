import express from "express";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();
const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3000;

// FatSecret OAuth2 credentials
const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;

let cachedToken = null;
let tokenExpiry = 0;

// 🔹 Token ophalen en cachen
async function getAccessToken() {
  const now = Date.now();
  if (cachedToken && now < tokenExpiry) {
    return cachedToken;
  }

  const resp = await axios.post(
    "https://oauth.fatsecret.com/connect/token",
    new URLSearchParams({
      grant_type: "client_credentials",
      scope: "basic",
    }),
    {
      auth: {
        username: CLIENT_ID,
        password: CLIENT_SECRET,
      },
    }
  );

  cachedToken = resp.data.access_token;
  tokenExpiry = now + resp.data.expires_in * 1000 - 5000; // 5 sec marge
  return cachedToken;
}

// 🔹 Proxy endpoint
app.get("/fatsecret", async (req, res) => {
  try {
    const { method, query } = req.query;
    if (!method) return res.status(400).json({ error: "Missing method param" });

    const token = await getAccessToken();

    const resp = await axios.get(
      `https://platform.fatsecret.com/rest/server.api?method=${method}&format=json&${query || ""}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    res.json(resp.data);
  } catch (err) {
    console.error(err.response?.data || err.message);
    res.status(500).json({ error: "Failed to fetch from FatSecret" });
  }
});

app.listen(PORT, () => console.log(`✅ Server running on port ${PORT}`));
