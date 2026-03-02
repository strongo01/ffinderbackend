from pydantic import BaseModel
from typing import Optional, List, Dict

class Nutriments(BaseModel):
    energy_kcal: Optional[float]
    fat: Optional[float]
    saturated_fat: Optional[float]
    carbohydrates: Optional[float]
    sugars: Optional[float]
    fiber: Optional[float]
    proteins: Optional[float]
    salt: Optional[float]


class Product(BaseModel):
    barcode: Optional[str]
    product_name: Optional[str]
    brands: Optional[str]
    nutriscore: Optional[str]
    serving_size: Optional[str]
    nutriments: Nutriments
    ingredients: Optional[str]
    vegan: bool
    vegetarian: bool
    image_url: Optional[str]


class ProductResponse(BaseModel):
    foods: Dict[str, List[Product]]