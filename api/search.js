import { callFatSecret } from "../lib/fatsecret.js";

export default async function handler(req, res) {
  const { query } = req.query;

  if (!query) {
    return res.status(400).json({ error: "query param ontbreekt" });
  }

  const data = await callFatSecret(
    { method: "foods.search", search_expression: query, format: "json", region: "nl" }
  );

  res.json(data);
}
