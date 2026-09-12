import { createWriteStream } from "node:fs";
import { createGzip } from "node:zlib";
import { pipeline } from "node:stream/promises";
import { MongoClient } from "mongodb";
import dotenv from "dotenv";

dotenv.config();
const output = process.argv[2] || "products.compact.jsonl";
const backup = process.argv[3] || "products.full.jsonl.gz";
const client = new MongoClient(process.env.MONGO_URI);
const compact = createWriteStream(output, { flags: "w" });
const full = createGzip({ level: 9 });
const fullFile = createWriteStream(backup, { flags: "w" });
full.pipe(fullFile);
const write = (stream, value) => new Promise((resolve, reject) => {
  if (stream.write(value)) resolve();
  else stream.once("drain", resolve);
  stream.once("error", reject);
});
function compactProduct(p) {
  const n = p.nutriments || {};
  const tags = Array.isArray(p.ingredients_analysis_tags) ? p.ingredients_analysis_tags : [];
  return {
    barcode: p.code || null,
    product_name: p.product_name || null,
    generic_name: p.generic_name || null,
    brands: p.brands || p.brand || null,
    quantity: p.quantity || null,
    serving_size: p.serving_size || p.serving_size_with_unit || p.serving_quantity || null,
    nutriscore: p.nutriscore_grade || null,
    energy_kcal: n["energy-kcal_100g"] ?? null,
    fat: n.fat_100g ?? null,
    saturated_fat: n["saturated-fat_100g"] ?? null,
    carbohydrates: n.carbohydrates_100g ?? null,
    sugars: n.sugars_100g ?? null,
    fiber: n.fiber_100g ?? null,
    proteins: n.proteins_100g ?? null,
    salt: n.salt_100g ?? null,
    ingredients: p.ingredients_text || null,
    vegan: tags.includes("en:vegan"),
    vegetarian: tags.includes("en:vegetarian"),
    image_url: p.image_url || p.image_front_url || p.selected_images?.front?.display?.en || p.image_front_small_url || p.image_small_url || null,
  };
}
let count = 0;
try {
  await client.connect();
  const cursor = client.db("off_db").collection("products").find({});
  for await (const p of cursor) {
    await write(compact, JSON.stringify(compactProduct(p)) + "\n");
    await write(full, JSON.stringify(p, (_, v) => typeof v === "bigint" ? Number(v) : v) + "\n");
    count++;
  }
  compact.end();
  full.end();
  await Promise.all([
    new Promise((r, j) => { compact.once("finish", r); compact.once("error", j); }),
    new Promise((r, j) => { fullFile.once("finish", r); fullFile.once("error", j); }),
  ]);
  console.log(JSON.stringify({ count, output, backup }));
} finally { await client.close(); }
