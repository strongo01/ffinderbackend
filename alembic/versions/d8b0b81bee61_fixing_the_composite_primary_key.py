"""fixing the composite primary key

Revision ID: d8b0b81bee61
Revises: 21f42cee44d8
Create Date: 2026-02-26 23:17:03.406603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8b0b81bee61'
down_revision: Union[str, Sequence[str], None] = '21f42cee44d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_constraint(
        "recipe_interactions_pkey",
        "recipe_interactions",
        type_="primary"
    )

    op.create_primary_key(
        "recipe_interactions_pkey",
        "recipe_interactions",
        ["user_id", "recipe_id"]
    )


def downgrade():
    op.drop_constraint(
        "recipe_interactions_pkey",
        "recipe_interactions",
        type_="primary"
    )

    op.create_primary_key(
        "recipe_interactions_pkey",
        "recipe_interactions",
        ["user_id"]
    )