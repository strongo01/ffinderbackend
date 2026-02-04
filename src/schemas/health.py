from pydantic import BaseModel

class HealthOk(BaseModel):
    status: str = "ok"