"""add creado_por to documentos

Revision ID: 002_add_creado_por
Revises: 001
Create Date: 2026-10-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Add creado_por column to documentos table
    op.add_column('documentos', 
        sa.Column('creado_por', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('personas.id', ondelete='SET NULL'), 
                  nullable=True))
    op.create_index('ix_documentos_creado_por', 'documentos', ['creado_por'])


def downgrade():
    op.drop_index('ix_documentos_creado_por', table_name='documentos')
    op.drop_column('documentos', 'creado_por')