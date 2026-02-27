from src.db.models import Recipe, Kitchen, Tag, Course, RecipeInteraction, User
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from src.schemas.recipes import RecipeSearchResult, RecipeSearch, RatingRequest

def search_recipes(payload: RecipeSearch, db: Session):
    ts_query = func.plainto_tsquery("english", payload.query)
    statement = (select(
        Recipe.id,
        Recipe.title,
        func.ts_rank(Recipe.search_vector, ts_query).label("rank")
    )
    .where(Recipe.search_vector.op("@@")(ts_query))
    .order_by(func.ts_rank(Recipe.search_vector, ts_query).desc())
    .limit(payload.limit)
    .offset(payload.offset))
    results = db.execute(statement).all()
    return results

def get_all_kitchens(db: Session):
    statement = select(Kitchen.name)
    return db.execute(statement).scalars().all()

def get_all_tags(db: Session):
    statement = select(Tag.sub)
    return db.execute(statement).scalars().all()

def get_all_courses(db: Session):
    statement = select(Course.main)
    return db.execute(statement).scalars().all()

def get_recipe_by_id(db: Session, id: int):
    return db.get(Recipe, id)

def rate_recipe(user_id: int, recipe_id: int, rating: float, db: Session):
    interaction = db.get(
        RecipeInteraction, (user_id, recipe_id)
    )
    if interaction:
        interaction.rating = rating
    else:
        interaction = RecipeInteraction(
            user_id=user_id,
            recipe_id=recipe_id,
            rating=rating
        )
        db.add(interaction)
    db.flush()

def get_user_by_firebase_id(firebase_uid: str, db: Session):
    statement = select(User).where(User.firebase_uid == firebase_uid)
    return db.execute(statement).scalar_one_or_none()

def create_user(firebase_uid: str, db: Session):
    obj = User(
        firebase_uid=firebase_uid
    )
    db.add(obj)
    db.flush()
    return obj

def get_user_interactions(db: Session, firebase_uid: str):
    user = get_user_by_firebase_id(firebase_uid=firebase_uid, db=db)
    if not user:
        return []
    return db.query(RecipeInteraction).filter_by(user_id=user.id).all()