from fastapi import HTTPException, status

class RecipeNotFound(Exception):
    pass

class InvalidAppKey(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing app key"
        )