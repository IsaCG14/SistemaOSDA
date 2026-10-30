"""
Database models for Office Secretary Document Agent.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, DateTime, Date, Integer, Float, Boolean,
    ForeignKey, UniqueConstraint, Index, JSON, Enum as SQLEnum,
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base

from app.db.base import Base


class DocumentState(str, PyEnum):
    """Estados válidos de un documento."""
    RECIBIDO = "RECIBIDO"
    EN_TRAMITE = "EN_TRAMITE"
    RESPONDIDO = "RESPONDIDO"
    ARCHIVADO = "ARCHIVADO"
    DERIVADO = "DERIVADO"
    RECHAZADO = "RECHAZADO"
    EXTRAVIADO = "EXTRAVIADO"


class DocumentType(str, PyEnum):
    """Tipos de documento válidos."""
    MEMO = "MEMO"
    OFICIO = "OFICIO"
    CIRCULAR = "CIRCULAR"
    INFORME = "INFORME"
    NOTA = "NOTA"
    ACTA = "ACTA"
    RESOLUCION = "RESOLUCION"
    SOLICITUD = "SOLICITUD"
    RECIBO = "RECIBO"
    OTRO = "OTRO"


class Priority(str, PyEnum):
    """Niveles de prioridad."""
    BAJA = "BAJA"
    NORMAL = "NORMAL"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


class Oficina(Base):
    """Catálogo de oficinas."""
    __tablename__ = "oficinas"
    
    sigla = Column(String(10), primary_key=True)
    nombre = Column(String(200), nullable=False)
    activa = Column(Boolean, default=True, nullable=False)
    creada_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizada_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    documentos_origen = relationship("Documento", foreign_keys="Documento.oficina_origen_sigla", back_populates="oficina_origen")
    documentos_destino = relationship("Documento", foreign_keys="Documento.oficina_destino_sigla", back_populates="oficina_destino")
    personas = relationship("Persona", back_populates="oficina")
    correlativos_reglas = relationship("CorrelativoRegla", back_populates="oficina")
    
    def __repr__(self):
        return f"<Oficina(sigla='{self.sigla}', nombre='{self.nombre}')>"


class Persona(Base):
    """Personas (remitentes, destinatarios, usuarios)."""
    __tablename__ = "personas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(200), nullable=False)
    cargo = Column(String(150), nullable=True)
    oficina_sigla = Column(String(10), ForeignKey("oficinas.sigla", ondelete="SET NULL"), nullable=True)
    telegram_user_id = Column(Integer, unique=True, nullable=True)
    email = Column(String(255), nullable=True)
    activa = Column(Boolean, default=True, nullable=False)
    creada_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizada_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    oficina = relationship("Oficina", back_populates="personas")
    documentos_remitente = relationship("Documento", foreign_keys="Documento.remitente_id", back_populates="remitente")
    documentos_destinatario = relationship("Documento", foreign_keys="Documento.destinatario_id", back_populates="destinatario")
    
    # Índices
    __table_args__ = (
        Index('ix_personas_nombre', 'nombre'),
        Index('ix_personas_oficina_sigla', 'oficina_sigla'),
        Index('ix_personas_telegram_user_id', 'telegram_user_id'),
    )
    
    def __repr__(self):
        return f"<Persona(nombre='{self.nombre}', cargo='{self.cargo}')>"


class TipoDocumento(Base):
    """Tipos de documento con sus reglas de correlativo."""
    __tablename__ = "tipos_documento"
    
    codigo = Column(String(20), primary_key=True)
    nombre = Column(String(100), nullable=False)
    prefijo_correlativo = Column(String(50), nullable=False)  # ej: "OTIC-MEMO"
    regla_secuencial = Column(JSONB, default={}, nullable=False)  # Configuración de secuencial
    plazo_dias_respuesta = Column(Integer, default=5, nullable=False)
    requiere_anexos = Column(Boolean, default=False, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    documentos = relationship("Documento", back_populates="tipo_documento")
    correlativos_reglas = relationship("CorrelativoRegla", back_populates="tipo_documento")
    
    def __repr__(self):
        return f"<TipoDocumento(codigo='{self.codigo}', nombre='{self.nombre}')>"


class CorrelativoRegla(Base):
    """Reglas de correlativo por oficina, tipo y año."""
    __tablename__ = "correlativos_reglas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oficina_sigla = Column(String(10), ForeignKey("oficinas.sigla", ondelete="CASCADE"), nullable=False)
    tipo_doc_codigo = Column(String(20), ForeignKey("tipos_documento.codigo", ondelete="CASCADE"), nullable=False)
    año = Column(Integer, nullable=False)
    ultimo_secuencial = Column(Integer, default=0, nullable=False)
    formato_salida = Column(String(100), nullable=False)  # ej: "{prefijo}-{año}-{secuencial:04d}"
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    oficina = relationship("Oficina", back_populates="correlativos_reglas")
    tipo_documento = relationship("TipoDocumento", back_populates="correlativos_reglas")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('oficina_sigla', 'tipo_doc_codigo', 'año', name='uq_correlativo_regla'),
        Index('ix_correlativo_regla_oficina_año', 'oficina_sigla', 'año'),
    )
    
    def __repr__(self):
        return f"<CorrelativoRegla(oficina='{self.oficina_sigla}', tipo='{self.tipo_doc_codigo}', año={self.año}, ultimo={self.ultimo_secuencial})>"


class Documento(Base):
    """Documento principal."""
    __tablename__ = "documentos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlativo = Column(String(100), unique=True, nullable=False, index=True)
    tipo_doc_codigo = Column(String(20), ForeignKey("tipos_documento.codigo", ondelete="RESTRICT"), nullable=False)
    oficina_origen_sigla = Column(String(10), ForeignKey("oficinas.sigla", ondelete="RESTRICT"), nullable=False)
    oficina_destino_sigla = Column(String(10), ForeignKey("oficinas.sigla", ondelete="RESTRICT"), nullable=False)
    fecha_documento = Column(Date, nullable=False, index=True)
    fecha_recepcion = Column(Date, nullable=True, index=True)
    remitente_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    destinatario_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    asunto = Column(Text, nullable=True)
    folios = Column(Integer, nullable=True)
    anexos = Column(JSONB, default=[], nullable=False)
    estado = Column(SQLEnum(DocumentState), default=DocumentState.RECIBIDO, nullable=False, index=True)
    prioridad = Column(SQLEnum(Priority), default=Priority.NORMAL, nullable=False)
    observaciones = Column(Text, nullable=True)
    confianza_ocr = Column(Float, nullable=True)
    confirmado_por = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    confirmado_en = Column(DateTime, nullable=True)
    creado_por = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    eliminado_en = Column(DateTime, nullable=True)  # Soft delete
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relaciones
    tipo_documento = relationship("TipoDocumento", back_populates="documentos")
    oficina_origen = relationship("Oficina", foreign_keys=[oficina_origen_sigla], back_populates="documentos_origen")
    oficina_destino = relationship("Oficina", foreign_keys=[oficina_destino_sigla], back_populates="documentos_destino")
    remitente = relationship("Persona", foreign_keys=[remitente_id], back_populates="documentos_remitente")
    destinatario = relationship("Persona", foreign_keys=[destinatario_id], back_populates="documentos_destinatario")
    adjuntos = relationship("Adjunto", back_populates="documento", cascade="all, delete-orphan")
    eventos_auditoria = relationship("EventoAuditoria", back_populates="documento", cascade="all, delete-orphan")
    raw_ocr = relationship("DocumentoRawOCR", back_populates="documento", uselist=False, cascade="all, delete-orphan")
    # Referencias a otros documentos
    respuestas = relationship(
        "Documento",
        secondary="documento_referencias",
        primaryjoin="Documento.id==DocumentoReferencia.documento_id",
        secondaryjoin="Documento.id==DocumentoReferencia.referencia_id",
        back_populates="referencias"
    )
    referencias = relationship(
        "Documento",
        secondary="documento_referencias",
        primaryjoin="Documento.id==DocumentoReferencia.referencia_id",
        secondaryjoin="Documento.id==DocumentoReferencia.documento_id",
        back_populates="respuestas"
    )
    
    # Índices compuestos
    __table_args__ = (
        Index('ix_documentos_fecha_documento', 'fecha_documento'),
        Index('ix_documentos_fecha_recepcion', 'fecha_recepcion'),
        Index('ix_documentos_oficina_origen_fecha', 'oficina_origen_sigla', 'fecha_documento'),
        Index('ix_documentos_oficina_destino_fecha', 'oficina_destino_sigla', 'fecha_documento'),
        Index('ix_documentos_estado_fecha', 'estado', 'fecha_recepcion'),
        Index('ix_documentos_eliminado', 'eliminado_en'),
        CheckConstraint("fecha_recepcion IS NULL OR fecha_recepcion >= fecha_documento", name="ck_fecha_recepcion_posterior"),
        CheckConstraint("folios IS NULL OR folios > 0", name="ck_folios_positivo"),
    )
    
    def __repr__(self):
        return f"<Documento(correlativo='{self.correlativo}', estado='{self.estado}')>"


class DocumentoReferencia(Base):
    """Tabla de relación para referencias entre documentos (respuestas, anexos, etc.)."""
    __tablename__ = "documento_referencias"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False)
    referencia_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False)
    tipo_referencia = Column(String(50), nullable=False)  # RESPONDE_A, REFERENCIA, ADJUNTA
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('documento_id', 'referencia_id', 'tipo_referencia', name='uq_documento_referencia'),
    )


class Adjunto(Base):
    """Archivos adjuntos a un documento."""
    __tablename__ = "adjuntos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False)
    storage_path = Column(String(500), nullable=False)  # Path en Supabase Storage
    mime_type = Column(String(100), nullable=False)
    tamano_bytes = Column(Integer, nullable=False)
    pagina_inicio = Column(Integer, default=1, nullable=False)
    pagina_fin = Column(Integer, nullable=True)
    es_original = Column(Boolean, default=True, nullable=False)  # True si es el archivo original subido
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones
    documento = relationship("Documento", back_populates="adjuntos")
    
    __table_args__ = (
        Index('ix_adjuntos_documento_id', 'documento_id'),
    )


class EventoAuditoria(Base):
    """Log de auditoría inmutable."""
    __tablename__ = "eventos_auditoria"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="SET NULL"), nullable=True)
    evento_tipo = Column(String(50), nullable=False)  # CREATED, UPDATED, STATE_CHANGE, VALIDATED, REJECTED, DELETED, OCR_PROCESSED
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    datos_anteriores = Column(JSONB, nullable=True)
    datos_nuevos = Column(JSONB, nullable=True)
    ip_origen = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones
    documento = relationship("Documento", back_populates="eventos_auditoria")
    usuario = relationship("Persona")
    
    __table_args__ = (
        Index('ix_eventos_auditoria_documento_creado', 'documento_id', 'creado_en'),
        Index('ix_eventos_auditoria_tipo_creado', 'evento_tipo', 'creado_en'),
    )


class DocumentoRawOCR(Base):
    """Datos crudos del OCR antes de validación humana."""
    __tablename__ = "documentos_raw_ocr"
    
    documento_id = Column(UUID(as_uuid=True), ForeignKey("documentos.id", ondelete="CASCADE"), primary_key=True)
    proveedor_vision = Column(String(50), nullable=False)  # ollama, google, azure, etc.
    modelo_vision = Column(String(100), nullable=False)
    respuesta_completa = Column(JSONB, nullable=False)
    score_global = Column(Float, nullable=False)
    scores_por_campo = Column(JSONB, default={}, nullable=False)
    procesado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    reintentos = Column(Integer, default=0, nullable=False)
    correcciones = Column(JSONB, default=[], nullable=False)  # Historial de correcciones humanas
    
    # Relaciones
    documento = relationship("Documento", back_populates="raw_ocr")