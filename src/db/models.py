from sqlalchemy import Column, Integer, Text, Index, ForeignKey, Table, Float, UniqueConstraint, String, DateTime, func
from src.db.base import Base
from sqlalchemy.dialects.postgresql import TSVECTOR, JSONB
from sqlalchemy.orm import relationship

recipe_tags = Table(
    "recipe_tags",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

recipe_kitchens = Table(
    "recipe_kitchens",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("kitchen_id", ForeignKey("kitchens.id"), primary_key=True),
)

recipe_courses = Table(
    "recipe_courses",
    Base.metadata,
    Column("recipe_id", ForeignKey("recipes.id"), primary_key=True),
    Column("course_id", ForeignKey("courses.id"), primary_key=True),
)


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)

    preparation_time = Column(Integer)
    total_time = Column(Integer)

    kcal = Column(Integer)
    fat = Column(Integer)
    saturated_fat = Column(Integer)
    carbs = Column(Integer)
    protein = Column(Integer)
    fibers = Column(Integer)
    salt = Column(Integer)

    persons = Column(Integer)
    url = Column(Text)

    steps = Column(JSONB)
    requirements = Column(JSONB)
    difficulty = Column(JSONB)

    search_vector = Column(TSVECTOR)

    recipe_ingredients = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan"
    )

    tags = relationship(
        "Tag",
        secondary=recipe_tags,
        back_populates="recipes"
    )

    kitchens = relationship(
        "Kitchen",
        secondary=recipe_kitchens,
        back_populates="recipes"
    )

    courses = relationship(
        "Course",
        secondary=recipe_courses,
        back_populates="recipes"
    )

    __table_args__ = (
        Index(
            "ix_recipes_search_vector",
            "search_vector",
            postgresql_using="gin"
        ),
    )

class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False)

    recipes = relationship(
        "RecipeIngredient",
        back_populates="ingredient"
    )

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    recipe_id = Column(ForeignKey("recipes.id"), primary_key=True)
    ingredient_id = Column(ForeignKey("ingredients.id"), primary_key=True)

    amount = Column(Float)
    unit = Column(Text)
    unit_abbreviation = Column(Text)
    postfix = Column(Text)

    recipe = relationship("Recipe", back_populates="recipe_ingredients")
    ingredient = relationship("Ingredient", back_populates="recipes")

    __table_args__ = (
        Index("ix_recipe_ingredients_ingredient_id", "ingredient_id"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    main = Column(Text)
    sub = Column(Text)

    recipes = relationship(
        "Recipe",
        secondary=recipe_tags,
        back_populates="tags"
    )

class Kitchen(Base):
    __tablename__ = "kitchens"

    id = Column(Integer, primary_key=True)
    main = Column(Text)
    sub = Column(Text)
    name = Column(Text)

    recipes = relationship(
        "Recipe",
        secondary=recipe_kitchens,
        back_populates="kitchens"
    )

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    main = Column(Text)
    sub = Column(Text)

    recipes = relationship(
        "Recipe",
        secondary=recipe_courses,
        back_populates="courses"
    )

# User stuff

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    firebase_uid = Column(String, unique=True, nullable=False, index=True)

    created_at = Column(DateTime, server_default=func.now())

    interactions = relationship("RecipeInteraction", back_populates="user")

class RecipeInteraction(Base):
    __tablename__ = "recipe_interactions"

    user_id = Column(ForeignKey("users.id"), primary_key=True)
    recipe_id = Column(ForeignKey("recipes.id"), primary_key=True)

    rating = Column(Float, nullable=True)

    user = relationship("User", back_populates="interactions")
