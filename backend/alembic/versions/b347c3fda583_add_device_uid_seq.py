"""add device_uid_seq

Revision ID: b347c3fda583
Revises: 142a7e77eb3b
Create Date: 2026-07-06 00:28:49.483893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b347c3fda583'
down_revision: Union[str, Sequence[str], None] = '142a7e77eb3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE device_uid_seq START 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE device_uid_seq")
