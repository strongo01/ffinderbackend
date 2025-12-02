import { callFatSecret } from "../lib/fatsecret.js";

export default async function handler(req, res) {
  try {
    const randomPage = Math.floor(Math.random() * 50) + 1;

    const search = await callFatSecret(
      {
        method: "recipes.search.v3",
        search_expression: "",
        page_number: randomPage,
        max_results: 20,
        format: "json",
        region: "nl"
      },
      `Recepten ophalen pagina ${randomPage}`
    );

    const list = search?.recipes?.recipe || [];

    if (!Array.isArray(list) || list.length === 0) {
      return res.json({ error: "Geen recepten ontvangen van FatSecret." });
    }

    const shuffled = [...list].sort(() => Math.random() - 0.5);
    const selected = shuffled.slice(0, 5);

    const detailPromises = selected.map(item => {
      if (!item.recipe_id) return null;

      return callFatSecret(
        {
          method: "recipe.get.v2",
          recipe_id: item.recipe_id,
          format: "json",
          region: "nl"
        },
        `Recept detail ${item.recipe_id}`
      );
    });

    const settled = await Promise.all(detailPromises);

    const results = settled
      .filter(v => v && v.recipe)
      .map(v => {
        const d = v.recipe;
        return {
          recipe_id: d.recipe_id ?? null,
          recipe_name: d.recipe_name ?? "",
          recipe_image: d.recipe_image ?? "",
          description: d.recipe_description ?? "",
          ingredients: d.recipe_ingredients?.ingredient || [],
          directions: d.recipe_directions || ""
        };
      });

    res.json({ recipes: results });
  } catch (err) {
    res.status(500).json({ error: err.message || String(err) });
  }
}
