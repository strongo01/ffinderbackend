from .health import router as health_router
from .recipes import router as recipes_router

routers = [health_router, recipes_router]