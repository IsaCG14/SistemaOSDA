"""
Seed data script for Office Secretary Document Agent.
Populates initial data: offices, document types, correlativo rules, persons.
"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.base import SessionLocal, engine, Base
from app.models import (
    Oficina, Persona, TipoDocumento, CorrelativoRegla,
    DocumentState, DocumentType, Priority
)
from app.core.config import settings


def create_tables():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas")


def seed_oficinas(db: Session):
    """Insertar catálogo de oficinas conocido."""
    oficinas = [
        {"sigla": "OTIC", "nombre": "Oficina de Tecnología de Información y Comunicación"},
        {"sigla": "OGA", "nombre": "Oficina de Gestión Administrativa"},
        {"sigla": "OGH", "nombre": "Oficina de Gestión Humana"},
        {"sigla": "OPP", "nombre": "Oficina de Planificación y Presupuesto"},
        {"sigla": "DP", "nombre": "Dirección de Planificación"},
        {"sigla": "DG", "nombre": "Dirección General"},
        {"sigla": "UAI", "nombre": "Unidad de Auditoría Interna"},
        {"sigla": "OAC", "nombre": "Oficina de Administración y Contabilidad"},
        {"sigla": "JUR", "nombre": "Asesoría Jurídica"},
        {"sigla": "COM", "nombre": "Oficina de Comunicaciones"},
    ]
    
    for of_data in oficinas:
        existing = db.query(Oficina).filter(Oficina.sigla == of_data["sigla"]).first()
        if not existing:
            oficina = Oficina(**of_data)
            db.add(oficina)
            print(f"  ✅ Oficina: {of_data['sigla']} - {of_data['nombre']}")
        else:
            print(f"  ⏭️  Oficina ya existe: {of_data['sigla']}")
    
    db.commit()


def seed_tipos_documento(db: Session):
    """Insertar tipos de documento con sus prefijos."""
    tipos = [
        {
            "codigo": "MEMO",
            "nombre": "Memorándum",
            "prefijo_correlativo": "{oficina}-MEMO",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 5,
            "requiere_anexos": False,
        },
        {
            "codigo": "OFICIO",
            "nombre": "Oficio",
            "prefijo_correlativo": "{oficina}-OFI",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 10,
            "requiere_anexos": False,
        },
        {
            "codigo": "CIRCULAR",
            "nombre": "Circular",
            "prefijo_correlativo": "{oficina}-CIR",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 3,
            "requiere_anexos": False,
        },
        {
            "codigo": "INFORME",
            "nombre": "Informe",
            "prefijo_correlativo": "{oficina}-INF",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 15,
            "requiere_anexos": True,
        },
        {
            "codigo": "NOTA",
            "nombre": "Nota / Nota de Entrega",
            "prefijo_correlativo": "{oficina}-NOTA",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 2,
            "requiere_anexos": False,
        },
        {
            "codigo": "ACTA",
            "nombre": "Acta",
            "prefijo_correlativo": "{oficina}-ACTA",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 0,
            "requiere_anexos": True,
        },
        {
            "codigo": "RESOLUCION",
            "nombre": "Resolución",
            "prefijo_correlativo": "{oficina}-RES",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 0,
            "requiere_anexos": False,
        },
        {
            "codigo": "SOLICITUD",
            "nombre": "Solicitud",
            "prefijo_correlativo": "{oficina}-SOL",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 10,
            "requiere_anexos": False,
        },
        {
            "codigo": "RECIBO",
            "nombre": "Recibo",
            "prefijo_correlativo": "{oficina}-REC",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 0,
            "requiere_anexos": False,
        },
        {
            "codigo": "OTRO",
            "nombre": "Otro tipo de documento",
            "prefijo_correlativo": "{oficina}-OTR",
            "regla_secuencial": {"formato": "{prefijo}-{año}-{secuencial:04d}", "reinicio_anual": True},
            "plazo_dias_respuesta": 5,
            "requiere_anexos": False,
        },
    ]
    
    for tipo_data in tipos:
        existing = db.query(TipoDocumento).filter(TipoDocumento.codigo == tipo_data["codigo"]).first()
        if not existing:
            tipo = TipoDocumento(**tipo_data)
            db.add(tipo)
            print(f"  ✅ Tipo: {tipo_data['codigo']} - {tipo_data['nombre']}")
        else:
            print(f"  ⏭️  Tipo ya existe: {tipo_data['codigo']}")
    
    db.commit()


def seed_correlativos_reglas(db: Session):
    """Crear reglas de correlativo para 2024, 2025, 2026."""
    from datetime import date
    años = [2024, 2025, 2026]
    
    oficinas = db.query(Oficina).filter(Oficina.activa == True).all()
    tipos = db.query(TipoDocumento).filter(TipoDocumento.activo == True).all()
    
    for oficina in oficinas:
        for tipo in tipos:
            for año in años:
                existing = db.query(CorrelativoRegla).filter(
                    CorrelativoRegla.oficina_sigla == oficina.sigla,
                    CorrelativoRegla.tipo_doc_codigo == tipo.codigo,
                    CorrelativoRegla.año == año
                ).first()
                
                if not existing:
                    prefijo = tipo.prefijo_correlativo.format(oficina=oficina.sigla)
                    regla = CorrelativoRegla(
                        oficina_sigla=oficina.sigla,
                        tipo_doc_codigo=tipo.codigo,
                        año=año,
                        ultimo_secuencial=0,
                        formato_salida=f"{prefijo}-{año}-{{secuencial:04d}}"
                    )
                    db.add(regla)
                    print(f"  ✅ Regla correlativo: {oficina.sigla}-{tipo.codigo}-{año}")
                else:
                    print(f"  ⏭️  Regla ya existe: {oficina.sigla}-{tipo.codigo}-{año}")
    
    db.commit()


def seed_personas(db: Session):
    """Insertar personas de ejemplo (datos ficticios)."""
    personas = [
        {
            "id": uuid.uuid4(),
            "nombre": "Secretaria Demo",
            "cargo": "Analista / Secretaria OTIC",
            "oficina_sigla": "OTIC",
            "telegram_user_id": None,  # Se llenará cuando se configure
            "email": "secretaria.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Registrador Demo",
            "cargo": "Receptor / Registrador OTIC",
            "oficina_sigla": "OTIC",
            "telegram_user_id": None,
            "email": "registrador.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Jefe OTIC Demo",
            "cargo": "Jefe OTIC",
            "oficina_sigla": "OTIC",
            "telegram_user_id": None,
            "email": "jefe.otic.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Jefe OGA Demo",
            "cargo": "Jefe OGA",
            "oficina_sigla": "OGA",
            "telegram_user_id": None,
            "email": "jefe.oga.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Analista OPP Demo",
            "cargo": "Planificación y Presupuesto",
            "oficina_sigla": "OPP",
            "telegram_user_id": None,
            "email": "analista.opp.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Directora General Demo",
            "cargo": "Directora General",
            "oficina_sigla": "DG",
            "telegram_user_id": None,
            "email": "directora.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Analista OGH Demo",
            "cargo": "Gestión Humana",
            "oficina_sigla": "OGH",
            "telegram_user_id": None,
            "email": "analista.ogh.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Analista de Sistemas Demo",
            "cargo": "Analista de Sistemas",
            "oficina_sigla": "OTIC",
            "telegram_user_id": None,
            "email": "analista.sistemas.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Auditor UAI Demo",
            "cargo": "Auditoría Interna",
            "oficina_sigla": "UAI",
            "telegram_user_id": None,
            "email": "auditor.demo@ejemplo.gob.ve",
        },
        {
            "id": uuid.uuid4(),
            "nombre": "Auditor Senior UAI Demo",
            "cargo": "Auditoría Interna",
            "oficina_sigla": "UAI",
            "telegram_user_id": None,
            "email": "auditor.senior.demo@ejemplo.gob.ve",
        },
    ]
    
    for pers_data in personas:
        existing = db.query(Persona).filter(Persona.email == pers_data["email"]).first()
        if not existing:
            persona = Persona(**pers_data)
            db.add(persona)
            print(f"  ✅ Persona: {pers_data['nombre']} ({pers_data['oficina_sigla']})")
        else:
            print(f"  ⏭️  Persona ya existe: {pers_data['nombre']}")
    
    db.commit()


def seed_documentos_ejemplo(db: Session):
    """Insertar documentos de ejemplo basados en los memos reales."""
    from datetime import date
    
    # Buscar IDs necesarios
    otic = db.query(Oficina).filter(Oficina.sigla == "OTIC").first()
    oga = db.query(Oficina).filter(Oficina.sigla == "OGA").first()
    opp = db.query(Oficina).filter(Oficina.sigla == "OPP").first()
    dg = db.query(Oficina).filter(Oficina.sigla == "DG").first()
    ogh = db.query(Oficina).filter(Oficina.sigla == "OGH").first()
    dp = db.query(Oficina).filter(Oficina.sigla == "DP").first()
    uai = db.query(Oficina).filter(Oficina.sigla == "UAI").first()
    
    jefe_otic = db.query(Persona).filter(Persona.nombre == "Jefe OTIC Demo").first()
    jefe_oga = db.query(Persona).filter(Persona.nombre == "Jefe OGA Demo").first()
    analista_opp = db.query(Persona).filter(Persona.nombre == "Analista OPP Demo").first()
    directora = db.query(Persona).filter(Persona.nombre == "Directora General Demo").first()
    analista_ogh = db.query(Persona).filter(Persona.nombre == "Analista OGH Demo").first()
    auditor = db.query(Persona).filter(Persona.nombre == "Auditor UAI Demo").first()
    auditor_sr = db.query(Persona).filter(Persona.nombre == "Auditor Senior UAI Demo").first()
    secretaria = db.query(Persona).filter(Persona.nombre == "Secretaria Demo").first()
    
    documentos = [
        {
            "correlativo": "OPP-022-2026-18/05",
            "tipo_doc_codigo": "MEMO",
            "oficina_origen_sigla": "OPP",
            "oficina_destino_sigla": "OTIC",
            "fecha_documento": date(2026, 5, 18),
            "fecha_recepcion": date(2026, 5, 18),
            "remitente_id": analista_opp.id if analista_opp else None,
            "destinatario_id": jefe_otic.id if jefe_otic else None,
            "asunto": "Solicitud de informes de gestión (ene-feb-mar-abr 2026)",
            "folios": 3,
            "anexos": [],
            "estado": "RECIBIDO",
            "prioridad": "NORMAL",
            "observaciones": "Copia a OGA (Jefe OGA)",
            "confianza_ocr": 0.95,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
        {
            "correlativo": "OGA-2026-158",
            "tipo_doc_codigo": "MEMO",
            "oficina_origen_sigla": "OGA",
            "oficina_destino_sigla": "OTIC",
            "fecha_documento": date(2026, 4, 22),
            "fecha_recepcion": date(2026, 4, 24),
            "remitente_id": jefe_oga.id if jefe_oga else None,
            "destinatario_id": jefe_otic.id if jefe_otic else None,
            "asunto": "Requerimientos para Auditoría Interna: habilitar módulos de comprobantes de órdenes de pago 2023-2025",
            "folios": 2,
            "anexos": [],
            "estado": "RECIBIDO",
            "prioridad": "ALTA",
            "observaciones": "Recibido: Registrador 24/04/2026",
            "confianza_ocr": 0.92,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
        {
            "correlativo": "UAI-2026-01",
            "tipo_doc_codigo": "NOTA",
            "oficina_origen_sigla": "UAI",
            "oficina_destino_sigla": "OGA",
            "fecha_documento": date(2026, 5, 7),
            "fecha_recepcion": date(2026, 5, 7),
            "remitente_id": auditor.id if auditor else None,
            "destinatario_id": jefe_oga.id if jefe_oga else None,
            "asunto": "Notificación de plazo adicional (3 días hábiles) por incumplimiento parcial",
            "folios": 1,
            "anexos": [],
            "estado": "EN_TRAMITE",
            "prioridad": "URGENTE",
            "observaciones": "Recibido: Registrador 3:17pm",
            "confianza_ocr": 0.88,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
        {
            "correlativo": "OGH-2026-062",
            "tipo_doc_codigo": "OFICIO",
            "oficina_origen_sigla": "OGH",
            "oficina_destino_sigla": "OTIC",
            "fecha_documento": date(2026, 4, 20),
            "fecha_recepcion": date(2026, 4, 24),
            "remitente_id": None,
            "destinatario_id": secretaria.id if secretaria else None,
            "asunto": "Solicitud de información sobre procedimiento administrativo interno (caso demo)",
            "folios": 4,
            "anexos": [],
            "estado": "RECIBIDO",
            "prioridad": "ALTA",
            "observaciones": "Recibido 24/04/2026",
            "confianza_ocr": 0.90,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
        {
            "correlativo": "DP-007-2026-24/03",
            "tipo_doc_codigo": "CIRCULAR",
            "oficina_origen_sigla": "DP",
            "oficina_destino_sigla": "OTIC",
            "fecha_documento": date(2026, 3, 24),
            "fecha_recepcion": date(2026, 3, 24),
            "remitente_id": analista_opp.id if analista_opp else None,
            "destinatario_id": jefe_otic.id if jefe_otic else None,
            "asunto": "Solicitud de informes de gestión ene-feb-mar, con plazo al 17/04/2026. A 7 oficinas (incluye OTIC)",
            "folios": 2,
            "anexos": [],
            "estado": "RESPONDIDO",
            "prioridad": "NORMAL",
            "observaciones": "Plazo al 17/04/2026",
            "confianza_ocr": 0.93,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
        {
            "correlativo": "OGH-2026-004",
            "tipo_doc_codigo": "CIRCULAR",
            "oficina_origen_sigla": "OGH",
            "oficina_destino_sigla": "OTIC",
            "fecha_documento": date(2026, 1, 9),
            "fecha_recepcion": date(2026, 1, 9),
            "remitente_id": analista_ogh.id if analista_ogh else None,
            "destinatario_id": jefe_otic.id if jefe_otic else None,
            "asunto": "Solicitud de programación de vacaciones pendientes. A todas las oficinas",
            "folios": 1,
            "anexos": [],
            "estado": "ARCHIVADO",
            "prioridad": "NORMAL",
            "observaciones": "",
            "confianza_ocr": 0.95,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
        {
            "correlativo": "DG-2026-002",
            "tipo_doc_codigo": "MEMO",
            "oficina_origen_sigla": "DG",
            "oficina_destino_sigla": "OTIC",
            "fecha_documento": date(2026, 1, 19),
            "fecha_recepcion": date(2026, 1, 19),
            "remitente_id": directora.id if directora else None,
            "destinatario_id": jefe_otic.id if jefe_otic else None,
            "asunto": "Solicitud de adquisición de tóner (OAC-2026-001)",
            "folios": 1,
            "anexos": ["OAC-2026-001"],
            "estado": "EN_TRAMITE",
            "prioridad": "NORMAL",
            "observaciones": "",
            "confianza_ocr": 0.91,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
        {
            "correlativo": "OTIC-2026-003",
            "tipo_doc_codigo": "NOTA",
            "oficina_origen_sigla": "OTIC",
            "oficina_destino_sigla": "OTIC",
            "fecha_documento": date(2026, 1, 8),
            "fecha_recepcion": date(2026, 1, 8),
            "remitente_id": jefe_otic.id if jefe_otic else None,
            "destinatario_id": None,
            "asunto": "Vacaciones del Analista de Sistemas (50 días, 12/01 al 24/03/2026, reincorporación 25/03/2026)",
            "folios": 1,
            "anexos": [],
            "estado": "ARCHIVADO",
            "prioridad": "NORMAL",
            "observaciones": "Interno OTIC",
            "confianza_ocr": 0.94,
            "confirmado_por": secretaria.id if secretaria else None,
            "confirmado_en": datetime.utcnow(),
        },
    ]
    
    for doc_data in documentos:
        existing = db.query(Documento).filter(Documento.correlativo == doc_data["correlativo"]).first()
        if not existing:
            documento = Documento(**doc_data)
            db.add(documento)
            print(f"  ✅ Documento: {doc_data['correlativo']} - {doc_data['asunto'][:50]}...")
        else:
            print(f"  ⏭️  Documento ya existe: {doc_data['correlativo']}")
    
    db.commit()


def main():
    """Ejecutar todo el seeding."""
    print("🌱 Iniciando seed data...")
    
    db = SessionLocal()
    try:
        create_tables()
        seed_oficinas(db)
        seed_tipos_documento(db)
        seed_correlativos_reglas(db)
        seed_personas(db)
        seed_documentos_ejemplo(db)
        print("\n✅ Seed data completado exitosamente")
    except Exception as e:
        print(f"\n❌ Error en seed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()