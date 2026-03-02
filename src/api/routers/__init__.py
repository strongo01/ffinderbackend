from .health import router as health_router
from .recipes import router as recipes_router
from .products import router as products_router

routers = [health_router, recipes_router, products_router]