from fastapi import APIRouter, Query
from src.services.products import search_products_service
from src.schemas.products import ProductResponse

router = APIRouter(
    prefix="/product",
    tags=["Products"],
)

@router.get("", response_model=ProductResponse)
async def get_product(q: str = Query(..., min_length=1)):
    return await search_products_service(query=q)
