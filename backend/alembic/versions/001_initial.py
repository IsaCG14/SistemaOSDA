"""
Initial migration - Create all tables for Office Secretary Document Agent.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─────────────────────────────────────────────────────────────────
    # OFICINAS
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'oficinas',
        sa.Column('sigla', sa.String(10), nullable=False),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('activa', sa.Boolean(), default=True, nullable=False),
        sa.Column('creada_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column('actualizada_en', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('sigla'),
    )

    # ─────────────────────────────────────────────────────────────────
    # PERSONAS
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'personas',
        sa.Column('id', UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('cargo', sa.String(150), nullable=True),
        sa.Column('oficina_sigla', sa.String(10), nullable=True),
        sa.Column('telegram_user_id', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('activa', sa.Boolean(), default=True, nullable=False),
        sa.Column('creada_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column('actualizada_en', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_user_id', name='uq_personas_telegram_user_id'),
    )
    op.create_foreign_key('fk_personas_oficina', 'personas', 'oficinas', ['oficina_sigla'], ['sigla'], ondelete='SET NULL')
    op.create_index('ix_personas_nombre', 'personas', ['nombre'])
    op.create_index('ix_personas_oficina_sigla', 'personas', ['oficina_sigla'])

    # ─────────────────────────────────────────────────────────────────
    # TIPOS DOCUMENTO
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'tipos_documento',
        sa.Column('codigo', sa.String(20), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('prefijo_correlativo', sa.String(50), nullable=False),
        sa.Column('regla_secuencial', JSONB(), default={}, nullable=False),
        sa.Column('plazo_dias_respuesta', sa.Integer(), default=5, nullable=False),
        sa.Column('requiere_anexos', sa.Boolean(), default=False, nullable=False),
        sa.Column('activo', sa.Boolean(), default=True, nullable=False),
        sa.Column('creado_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('codigo'),
    )

    # ─────────────────────────────────────────────────────────────────
    # CORRELATIVOS REGLAS
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'correlativos_reglas',
        sa.Column('id', UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('oficina_sigla', sa.String(10), nullable=False),
        sa.Column('tipo_doc_codigo', sa.String(20), nullable=False),
        sa.Column('año', sa.Integer(), nullable=False),
        sa.Column('ultimo_secuencial', sa.Integer(), default=0, nullable=False),
        sa.Column('formato_salida', sa.String(100), nullable=False),
        sa.Column('creado_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['oficina_sigla'], ['oficinas.sigla'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tipo_doc_codigo'], ['tipos_documento.codigo'], ondelete='CASCADE'),
        sa.UniqueConstraint('oficina_sigla', 'tipo_doc_codigo', 'año', name='uq_correlativo_regla'),
    )
    op.create_index('ix_correlativo_regla_oficina_año', 'correlativos_reglas', ['oficina_sigla', 'año'])

    # ─────────────────────────────────────────────────────────────────
    # DOCUMENTOS
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'documentos',
        sa.Column('id', UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('correlativo', sa.String(100), nullable=False),
        sa.Column('tipo_doc_codigo', sa.String(20), nullable=False),
        sa.Column('oficina_origen_sigla', sa.String(10), nullable=False),
        sa.Column('oficina_destino_sigla', sa.String(10), nullable=False),
        sa.Column('fecha_documento', sa.Date(), nullable=False),
        sa.Column('fecha_recepcion', sa.Date(), nullable=True),
        sa.Column('remitente_id', UUID(as_uuid=True), nullable=True),
        sa.Column('destinatario_id', UUID(as_uuid=True), nullable=True),
        sa.Column('asunto', sa.Text(), nullable=True),
        sa.Column('folios', sa.Integer(), nullable=True),
        sa.Column('anexos', JSONB(), default=[], nullable=False),
        sa.Column('estado', sa.String(20), default='RECIBIDO', nullable=False),
        sa.Column('prioridad', sa.String(20), default='NORMAL', nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('confianza_ocr', sa.Float(), nullable=True),
        sa.Column('confirmado_por', UUID(as_uuid=True), nullable=True),
        sa.Column('confirmado_en', sa.DateTime(), nullable=True),
        sa.Column('eliminado_en', sa.DateTime(), nullable=True),
        sa.Column('creado_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('correlativo', name='uq_documentos_correlativo'),
        sa.ForeignKeyConstraint(['tipo_doc_codigo'], ['tipos_documento.codigo'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['oficina_origen_sigla'], ['oficinas.sigla'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['oficina_destino_sigla'], ['oficinas.sigla'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['remitente_id'], ['personas.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['destinatario_id'], ['personas.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['confirmado_por'], ['personas.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_documentos_fecha_documento', 'documentos', ['fecha_documento'])
    op.create_index('ix_documentos_fecha_recepcion', 'documentos', ['fecha_recepcion'])
    op.create_index('ix_documentos_oficina_origen_fecha', 'documentos', ['oficina_origen_sigla', 'fecha_documento'])
    op.create_index('ix_documentos_oficina_destino_fecha', 'documentos', ['oficina_destino_sigla', 'fecha_documento'])
    op.create_index('ix_documentos_estado_fecha', 'documentos', ['estado', 'fecha_recepcion'])
    op.create_index('ix_documentos_eliminado', 'documentos', ['eliminado_en'])

    # Check constraints
    op.create_check_constraint(
        'ck_fecha_recepcion_posterior',
        'documentos',
        'fecha_recepcion IS NULL OR fecha_recepcion >= fecha_documento'
    )
    op.create_check_constraint(
        'ck_folios_positivo',
        'documentos',
        'folios IS NULL OR folios > 0'
    )
    op.create_check_constraint(
        'ck_estado_valido',
        'documentos',
        "estado IN ('RECIBIDO','EN_TRAMITE','RESPONDIDO','ARCHIVADO','DERIVADO','RECHAZADO','EXTRAVIADO')"
    )
    op.create_check_constraint(
        'ck_prioridad_valida',
        'documentos',
        "prioridad IN ('BAJA','NORMAL','ALTA','URGENTE')"
    )

    # ─────────────────────────────────────────────────────────────────
    # DOCUMENTO REFERENCIAS (respuestas, anexos, referencias)
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'documento_referencias',
        sa.Column('id', UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('documento_id', UUID(as_uuid=True), nullable=False),
        sa.Column('referencia_id', UUID(as_uuid=True), nullable=False),
        sa.Column('tipo_referencia', sa.String(50), nullable=False),
        sa.Column('creado_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['referencia_id'], ['documentos.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('documento_id', 'referencia_id', 'tipo_referencia', name='uq_documento_referencia'),
    )

    # ─────────────────────────────────────────────────────────────────
    # ADJUNTOS
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'adjuntos',
        sa.Column('id', UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('documento_id', UUID(as_uuid=True), nullable=False),
        sa.Column('storage_path', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('tamano_bytes', sa.Integer(), nullable=False),
        sa.Column('pagina_inicio', sa.Integer(), default=1, nullable=False),
        sa.Column('pagina_fin', sa.Integer(), nullable=True),
        sa.Column('es_original', sa.Boolean(), default=True, nullable=False),
        sa.Column('creado_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_adjuntos_documento_id', 'adjuntos', ['documento_id'])

    # ─────────────────────────────────────────────────────────────────
    # EVENTOS AUDITORIA
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'eventos_auditoria',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('documento_id', UUID(as_uuid=True), nullable=True),
        sa.Column('evento_tipo', sa.String(50), nullable=False),
        sa.Column('usuario_id', UUID(as_uuid=True), nullable=True),
        sa.Column('datos_anteriores', JSONB(), nullable=True),
        sa.Column('datos_nuevos', JSONB(), nullable=True),
        sa.Column('ip_origen', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('creado_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['usuario_id'], ['personas.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_eventos_auditoria_documento_creado', 'eventos_auditoria', ['documento_id', 'creado_en'])
    op.create_index('ix_eventos_auditoria_tipo_creado', 'eventos_auditoria', ['evento_tipo', 'creado_en'])

    # ─────────────────────────────────────────────────────────────────
    # DOCUMENTOS RAW OCR
    # ─────────────────────────────────────────────────────────────────
    op.create_table(
        'documentos_raw_ocr',
        sa.Column('documento_id', UUID(as_uuid=True), nullable=False),
        sa.Column('proveedor_vision', sa.String(50), nullable=False),
        sa.Column('modelo_vision', sa.String(100), nullable=False),
        sa.Column('respuesta_completa', JSONB(), nullable=False),
        sa.Column('score_global', sa.Float(), nullable=False),
        sa.Column('scores_por_campo', JSONB(), default={}, nullable=False),
        sa.Column('procesado_en', sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column('reintentos', sa.Integer(), default=0, nullable=False),
        sa.Column('correcciones', JSONB(), default=[], nullable=False),
        sa.PrimaryKeyConstraint('documento_id'),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table('documentos_raw_ocr')
    op.drop_table('eventos_auditoria')
    op.drop_table('adjuntos')
    op.drop_table('documento_referencias')
    op.drop_table('documentos')
    op.drop_table('correlativos_reglas')
    op.drop_table('tipos_documento')
    op.drop_table('personas')
    op.drop_table('oficinas')