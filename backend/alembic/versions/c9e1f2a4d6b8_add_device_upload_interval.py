"""Add upload_interval_seconds to devices

Revision ID: c9e1f2a4d6b8
Revises: 8d4b5878d7a9
Create Date: 2026-07-06 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e1f2a4d6b8'
down_revision: Union[str, Sequence[str], None] = '8d4b5878d7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'devices',
        sa.Column('upload_interval_seconds', sa.Integer(), server_default='300', nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('devices', 'upload_interval_seconds')
