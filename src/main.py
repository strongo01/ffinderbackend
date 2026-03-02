from fastapi import FastAPI, Depends
from src.api.routers import routers
from contextlib import asynccontextmanager
import src.startup as startup
from src.core.security import verify_app_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    recipe_matrix, recipe_ids, id_to_index, recipe_cache = startup.load_recipe_matrix()
    app.state.recipe_matrix = recipe_matrix
    app.state.recipe_ids = recipe_ids
    app.state.id_to_index = id_to_index
    app.state.recipe_cache = recipe_cache
    yield

app = FastAPI(lifespan=lifespan, dependencies=[Depends(verify_app_key)])

for router in routers:
    app.include_router(router)