"""Create the local Firebase user profile table."""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_user"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("alergias", sa.JSON(), nullable=True),
        sa.Column("objetivos_nutricionales", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("firebase_uid"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_firebase_uid", "user", ["firebase_uid"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_firebase_uid", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")