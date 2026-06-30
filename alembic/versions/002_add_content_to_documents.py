"""Add content column to documents table

Revision ID: 002_add_content
Revises: 506e088bc6de
Create Date: 2026-06-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_content'
down_revision: Union[str, Sequence[str], None] = '506e088bc6de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add content column to documents table for storing raw document text."""
    op.add_column('documents', sa.Column('content', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove content column from documents table."""
    op.drop_column('documents', 'content')
