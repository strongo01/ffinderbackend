from pydantic import BaseModel, Field
from typing import Optional

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
    