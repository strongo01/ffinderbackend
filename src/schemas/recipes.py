from pydantic import BaseModel, Field
from typing import Optional, List

class RecipeSearch(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)
    kitchen: Optional[str] = None
    course: Optional[str] = None

class RecipeSearchResult(BaseModel):
    id: int
    title: str
    rank: float

class FiltersResult(BaseModel):
    kitchens: List[str]
    courses: List[str]
    tags: List[str]
    difficulties: List[str] = ["eenvoudig", "gemiddeld", "uitdagend"]
    max_kcal: int = 1500
    max_prep_time: int = 120

class IdSearch(BaseModel):
    id: int


# Nested models for recipe

class IngredientBase(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

class RecipeIngredientBase(BaseModel):
    ingredient: IngredientBase
    amount: float
    unit: Optional[str]
    unit_abbreviation: Optional[str]
    postfix: Optional[str]

    class Config:
        orm_mode = True

class TagBase(BaseModel):
    id: int
    main: str
    sub: str

    class Config:
        orm_mode = True

class KitchenBase(BaseModel):
    id: int
    main: str
    sub: Optional[str]
    name: str

    class Config:
        orm_mode = True

class CourseBase(BaseModel):
    id: int
    main: str
    sub: Optional[str]

    class Config:
        orm_mode = True

class RecipeResponse(BaseModel):
    id: int
    title: str
    preparation_time: Optional[int]
    total_time: Optional[int]

    kcal: Optional[int]
    fat: Optional[int]
    saturated_fat: Optional[int]
    carbs: Optional[int]
    protein: Optional[int]
    fibers: Optional[int]
    salt: Optional[int]

    persons: Optional[int]
    url: Optional[str]

    steps: Optional[list] = Field(default_factory=list)
    requirements: Optional[list] = Field(default_factory=list)
    difficulty: Optional[dict] = Field(default_factory=dict)

    recipe_ingredients: List[RecipeIngredientBase] = Field(default_factory=list)
    tags: List[TagBase] = Field(default_factory=list)
    kitchens: List[KitchenBase] = Field(default_factory=list)
    courses: List[CourseBase] = Field(default_factory=list)

    class Config:
        orm_mode = True