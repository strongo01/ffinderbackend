import os
from pymongo import AsyncMongoClient
from pymongo.server_api import ServerApi

MONGO_URI = os.getenv("MONGO_URI")

client = AsyncMongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client["off_db"]

def get_products_collection():
    return db["products"]