import re
from typing import List, Optional
from src.db.mongo import get_products_collection
from src.schemas.products import Product, ProductResponse


def is_barcode(value: str):
    return bool(re.fullmatch(r"[0-9]{8,14}", value))


def format_product(p: dict):
    if not p:
        return None

    n = p.get("nutriments", {})
    tags = p.get("ingredients_analysis_tags") or []

    image_url = (
        p.get("image_url")
        or p.get("image_front_url")
        or p.get("selected_images", {}).get("front", {}).get("display", {}).get("en")
        or p.get("image_front_small_url")
        or p.get("image_small_url")
    )

    serving_size = (
        p.get("serving_size")
        or p.get("serving_size_with_unit")
        or p.get("serving_quantity")
    )

    return {
        "barcode": p.get("code"),
        "product_name": p.get("product_name"),
        "brands": p.get("brands") or p.get("brand"),
        "nutriscore": p.get("nutriscore_grade"),
        "serving_size": serving_size,
        "nutriments": {
            "energy_kcal": n.get("energy-kcal_100g"),
            "fat": n.get("fat_100g"),
            "saturated_fat": n.get("saturated-fat_100g"),
            "carbohydrates": n.get("carbohydrates_100g"),
            "sugars": n.get("sugars_100g"),
            "fiber": n.get("fiber_100g"),
            "proteins": n.get("proteins_100g"),
            "salt": n.get("salt_100g"),
        },
        "ingredients": p.get("ingredients_text"),
        "vegan": "en:vegan" in tags,
        "vegetarian": "en:vegetarian" in tags,
        "image_url": image_url,
    }

async def search_products_service(query: str):
    collection = get_products_collection()
    results: List[Product] = []

    if is_barcode(query):
        product_doc = await collection.find_one({"code": query})
        if product_doc:
            results.append(Product(**format_product(product_doc)))
    else:
        escaped = re.escape(query)
        regex_pattern = "|".join(escaped.split(" "))
        regex = {"$regex": regex_pattern, "$options": "i"}

        cursor = collection.find(
            {
                "$or": [
                    {"product_name": regex},
                    {"generic_name": regex},
                    {"brands": regex},
                ]
            }
        ).limit(50)

        async for doc in cursor:
            formatted = format_product(doc)
            if formatted:
                results.append(Product(**formatted))

    return ProductResponse(foods={"food": results})