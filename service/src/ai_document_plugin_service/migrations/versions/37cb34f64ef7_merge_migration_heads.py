"""Merge migration heads

Revision ID: 37cb34f64ef7
Revises: 20261002_01, 20261007_01
Create Date: 2026-10-16 11:50:50.872807
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = '37cb34f64ef7'
down_revision = ('20261002_01', '20261007_01')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass
