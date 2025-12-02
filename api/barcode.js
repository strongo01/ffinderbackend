import { callOpenFoodFacts } from "../lib/fatsecret.js";

export default async function handler(req, res) {
  const { code } = req.query;

  if (!code) {
    return res.status(400).json({ error: "code param ontbreekt" });
  }

  const data = await callOpenFoodFacts(code);

  res.json(data);
}
