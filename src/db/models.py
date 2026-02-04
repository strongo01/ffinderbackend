from sqlalchemy import Column, Integer, Text, ARRAY, Index
from src.db.base import Base
from sqlalchemy.dialects.postgresql import TSVECTOR

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)

    ingredients = Column(ARRAY(Text), nullable=False)
    tags = Column(ARRAY(Text), nullable=False)
    kitchen = Column(ARRAY(Text), nullable=False)
    course = Column(ARRAY(Text), nullable=False)

    search_vector = Column(TSVECTOR)

    __table_args__ = (
        Index(
            "ix_recipes_search_vector",
            "search_vector",
            postgresql_using="gin"
        ),
    )