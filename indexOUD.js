import express from "express";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();

const app = express();

app.use(express.json());

// CORS + OPTIONS handling
app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", req.headers.origin || "*");
    res.header("Access-Control-Allow-Headers", "Content-Type, x-app-key");
    res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");

    if (req.method === "OPTIONS") return res.sendStatus(200);
    next();
});

// Validate x-app-key (except OPTIONS)
function validateAppKey(req, res, next) {
    const key = req.headers["x-app-key"];
    if (!key || key !== process.env.APP_KEY) {
        return res.status(401).json({ error: "Unauthorized: invalid app key" });
    }
    next();
}

app.use((req, res, next) => {
    if (req.method === "OPTIONS") return next();
    validateAppKey(req, res, next);
});


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
        new URLSearchParams({ grant_type: "client_credentials", scope: "premier" }),
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

async function translateToEnglish(text) {
    try {
        const resp = await axios.post(
            "https://translate.argosopentech.com/translate",
            {
                q: text,
                source: "nl",
                target: "en",
                format: "text"
            },
            { headers: { "Content-Type": "application/json" } }
        );

        console.log(`🔹 Vertaling: "${text}" -> "${resp.data.translatedText}"`);
        return resp.data.translatedText;
    } catch (err) {
        console.error("Fout bij vertalen:", err.response?.data || err.message);
        return text;
    }
}



app.get("/search", async (req, res) => {
    const { query } = req.query;
    if (!query) return res.status(400).json({ error: "query param ontbreekt" });

    const translatedQuery = await translateToEnglish(query);


    const data = await callFatSecret(
        {
            method: "foods.search.v4", // V2 is prima
            search_expression: translatedQuery,
            format: "json",
            region: "NL",
            language: "nl",    // Deze zorgt dat je 'Appel' krijgt i.p.v. 'Apple'
            max_results: 50,
            page_number: 0,
        },
       `Zoeken op naam (vertaald): ${query} -> ${translatedQuery}`
    );
    res.json(data);
});

app.get("/recipe", async (req, res) => {
    const { query } = req.query;
    if (!query) return res.status(400).json({ error: "query param ontbreekt" });
    const data = await callFatSecret(
        {
            method: "recipes.search.v3", search_expression: query, format: "json", region: "NL",
            language: "nl",
        },
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


app.get("/recipes/random", async (req, res) => {
    try {
        console.log("🔄 Willekeurige recepten ophalen...");

        const randomPage = Math.floor(Math.random() * 50) + 1;
        console.log(`📄 Random pagina: ${randomPage}`);

        const search = await callFatSecret(
            {
                method: "recipes.search.v3",
                search_expression: "",
                page_number: randomPage,
                max_results: 20,
                format: "json",
                region: "NL",
                language: "nl",
            },
            `Recepten ophalen pagina ${randomPage}`
        );

        const list = search?.recipes?.recipe || [];

        if (!Array.isArray(list) || list.length === 0) {
            return res.status(200).json({ error: "Geen recepten ontvangen van FatSecret." });
        }

        const shuffled = [...list].sort(() => Math.random() - 0.5);
        const selected = shuffled.slice(0, 5);

        const detailPromises = selected.map(item => {
            const id = item.recipe_id;
            if (!id) return Promise.resolve(null);

            return callFatSecret(
                {
                    method: "recipe.get.v2",
                    recipe_id: id,
                    format: "json",
                    region: "NL",
                    language: "nl",
                },
                `Recept detail ${id}`
            ).catch(err => {
                console.error(`Detail fetch failed for ${id}:`, err);
                return null;
            });
        });

        const settled = await Promise.allSettled(detailPromises);

        const results = settled
            .filter(s => s.status === "fulfilled" && s.value && s.value.recipe)
            .map(s => {
                const data = s.value.recipe;
                return {
                    recipe_id: data.recipe_id ?? data.recipeId ?? null,
                    recipe_name: data.recipe_name ?? data.recipe_name ?? data.recipe_title ?? '',
                    recipe_image: data.recipe_image ?? data.recipeImage ?? '',
                    description: data.recipe_description ?? data.description ?? '',
                    ingredients: (data.recipe_ingredients?.ingredient) || data.ingredients || [],
                    directions: data.recipe_directions ?? data.directions ?? data.directions_list ?? '',
                };
            });

        res.json({ recipes: results });

    } catch (err) {
        console.error("Fout bij random recipes:", err);
        res.status(500).json({ error: err.message || String(err) });
    }
});




app.listen(PORT, () => console.log(`✅ Server running on port ${PORT}`));