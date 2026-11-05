"""
Graphify Service - Main entry point for the Graphify API service.
Connects Neo4j with the document data model.
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from neo4j import GraphDatabase, Driver
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphify_password")
GRAPHIFY_INDEX_NAME = os.getenv("GRAPHIFY_INDEX_NAME", "osda_docs")
GRAPHIFY_EMBEDDING_MODEL = os.getenv("GRAPHIFY_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
GRAPHIFY_EMBEDDING_DIM = int(os.getenv("GRAPHIFY_EMBEDDING_DIM", "384"))
GRAPHIFY_API_PORT = int(os.getenv("GRAPHIFY_API_PORT", "8080"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

driver: Optional[Driver] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver
    logger.info("Conectando a Neo4j...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        logger.info("✅ Conexión a Neo4j establecida")
        await create_schema()
    except Exception as e:
        logger.error(f"❌ Error conectando a Neo4j: {e}")
        raise
    yield
    logger.info("Cerrando conexión a Neo4j...")
    if driver:
        driver.close()


app = FastAPI(
    title="Graphify API",
    description="API para consultas de grafos sobre documentos, oficinas y personas",
    version="1.0.0",
    lifespan=lifespan
)


async def create_schema():
    """Crear constraints e índices en Neo4j."""
    queries = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Documento) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Oficina) REQUIRE o.sigla IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Persona) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:TipoDocumento) REQUIRE t.codigo IS UNIQUE",
        "CREATE INDEX IF NOT EXISTS FOR (d:Documento) ON (d.correlativo)",
        "CREATE INDEX IF NOT EXISTS FOR (d:Documento) ON (d.fecha_documento)",
        "CREATE INDEX IF NOT EXISTS FOR (d:Documento) ON (d.estado)",
        "CREATE INDEX IF NOT EXISTS FOR (d:Documento) ON (d.oficina_origen_sigla)",
        "CREATE INDEX IF NOT EXISTS FOR (d:Documento) ON (d.oficina_destino_sigla)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Persona) ON (p.nombre)",
        "CREATE INDEX IF NOT EXISTS FOR (o:Oficina) ON (o.nombre)",
    ]
    
    with driver.session() as session:
        for query in queries:
            try:
                session.run(query)
                logger.info(f"Schema: {query[:60]}...")
            except Exception as e:
                logger.warning(f"Schema query warning: {e}")


def get_driver() -> Driver:
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j no disponible")
    return driver


# ─────────────────────────────────────────────────────────────────
# MODELOS PYDANTIC
# ─────────────────────────────────────────────────────────────────

class DocumentoBase(BaseModel):
    correlativo: str
    tipo_documento: str
    oficina_origen: str
    oficina_destino: str
    fecha_documento: str
    fecha_recepcion: Optional[str] = None
    remitente: Optional[str] = None
    destinatario: Optional[str] = None
    asunto: Optional[str] = None
    folios: Optional[int] = None
    anexos: Optional[List[str]] = None
    estado: str = "RECIBIDO"
    prioridad: Optional[str] = "NORMAL"
    observaciones: Optional[str] = None
    confianza_ocr: Optional[float] = None


class DocumentoCreate(DocumentoBase):
    id: str


class DocumentoResponse(BaseModel):
    """Refleja las propiedades tal como las guarda el nodo en Neo4j."""
    id: str
    correlativo: str
    tipo_documento: str
    oficina_origen_sigla: str
    oficina_destino_sigla: str
    # Neo4j devuelve tipos nativos (Date/DateTime): se dejan como Any
    fecha_documento: Any
    fecha_recepcion: Optional[Any] = None
    remitente: Optional[str] = None
    destinatario: Optional[str] = None
    asunto: Optional[str] = None
    folios: Optional[int] = None
    anexos: Optional[List[str]] = None
    estado: str = "RECIBIDO"
    prioridad: Optional[str] = "NORMAL"
    observaciones: Optional[str] = None
    confianza_ocr: Optional[float] = None
    created_at: Any
    updated_at: Optional[Any] = None


class TraceResult(BaseModel):
    documento: Dict[str, Any]
    respuestas: List[Dict[str, Any]] = []
    referencias: List[Dict[str, Any]] = []
    anexos: List[Dict[str, Any]] = []
    flujo_oficinas: List[Dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def to_plain(obj):
    """Convierte tipos nativos de Neo4j (Date/DateTime/etc) a tipos JSON-safe."""
    from neo4j.time import Date, DateTime
    if isinstance(obj, (Date, DateTime)):
        return str(obj)
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    return obj


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    try:
        if driver:
            driver.verify_connectivity()
            return {"status": "healthy", "neo4j": "connected"}
        return {"status": "unhealthy", "neo4j": "disconnected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/documentos", response_model=DocumentoResponse, status_code=201)
async def create_documento(doc: DocumentoCreate, drv: Driver = Depends(get_driver)):
    query = """
    MERGE (d:Documento {id: $id})
    SET d.correlativo = $correlativo,
        d.tipo_documento = $tipo_documento,
        d.oficina_origen_sigla = $oficina_origen,
        d.oficina_destino_sigla = $oficina_destino,
        d.fecha_documento = date($fecha_documento),
        d.fecha_recepcion = CASE WHEN $fecha_recepcion IS NOT NULL THEN date($fecha_recepcion) ELSE null END,
        d.remitente = $remitente,
        d.destinatario = $destinatario,
        d.asunto = $asunto,
        d.folios = $folios,
        d.anexos = $anexos,
        d.estado = $estado,
        d.prioridad = $prioridad,
        d.observaciones = $observaciones,
        d.confianza_ocr = $confianza_ocr,
        d.created_at = datetime(),
        d.updated_at = datetime()
    
    MERGE (oo:Oficina {sigla: $oficina_origen})
    MERGE (d)-[:ENVIA]->(oo)
    MERGE (od:Oficina {sigla: $oficina_destino})
    MERGE (d)-[:RECIBE]->(od)
    MERGE (td:TipoDocumento {codigo: $tipo_documento})
    MERGE (td)-[:CLASIFICA]->(d)
    
    RETURN d
    """
    
    with drv.session() as session:
        result = session.run(query, **doc.model_dump())
        record = result.single()
        if record:
            return DocumentoResponse(**to_plain(dict(record["d"])))
        raise HTTPException(status_code=500, detail="Error creando documento")


@app.get("/trace/{correlativo}", response_model=TraceResult)
async def trace_documento(correlativo: str, drv: Driver = Depends(get_driver)):
    doc_query = "MATCH (d:Documento {correlativo: $correlativo}) RETURN d"
    with drv.session() as session:
        doc_result = session.run(doc_query, correlativo=correlativo)
        doc_record = doc_result.single()
        if not doc_record:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        documento = dict(doc_record["d"])
    
    respuestas_query = """
    MATCH (d:Documento {correlativo: $correlativo})<-[:RESPONDE_A]-(r:Documento)
    RETURN r ORDER BY r.fecha_documento DESC
    """
    referencias_query = """
    MATCH (d:Documento {correlativo: $correlativo})-[:REFERENCIA]->(ref:Documento)
    RETURN ref
    """
    anexos_query = """
    MATCH (d:Documento {correlativo: $correlativo})-[:ADJUNTA]->(a:Documento)
    RETURN a
    """
    flujo_query = """
    MATCH (d:Documento {correlativo: $correlativo})
    OPTIONAL MATCH (d)-[:ENVIA]->(oo:Oficina)
    OPTIONAL MATCH (d)-[:RECIBE]->(od:Oficina)
    OPTIONAL MATCH (d)-[:ENVIA]->(oo)<-[:PERTENECE_A]-(p:Persona)
    OPTIONAL MATCH (d)-[:RECIBE]->(od)<-[:PERTENECE_A]-(p2:Persona)
    RETURN oo, od, collect(DISTINCT p) as personas_origen, collect(DISTINCT p2) as personas_destino
    """
    
    with drv.session() as session:
        respuestas = [dict(r["r"]) for r in session.run(respuestas_query, correlativo=correlativo)]
        referencias = [dict(r["ref"]) for r in session.run(referencias_query, correlativo=correlativo)]
        anexos = [dict(r["a"]) for r in session.run(anexos_query, correlativo=correlativo)]
        flujo_result = session.run(flujo_query, correlativo=correlativo).single()
    
    flujo_oficinas = []
    if flujo_result:
        flujo_oficinas = [
            {"tipo": "origen", "oficina": dict(flujo_result["oo"]), "personas": [dict(p) for p in flujo_result["personas_origen"]]},
            {"tipo": "destino", "oficina": dict(flujo_result["od"]), "personas": [dict(p) for p in flujo_result["personas_destino"]]}
        ]
    
    return TraceResult(
        documento=to_plain(documento),
        respuestas=to_plain(respuestas),
        referencias=to_plain(referencias),
        anexos=to_plain(anexos),
        flujo_oficinas=to_plain(flujo_oficinas)
    )


@app.get("/consultas/pendientes")
async def get_pendientes(dias_limite: int = Query(5, ge=1), drv: Driver = Depends(get_driver)):
    query = """
    MATCH (d:Documento)
    WHERE d.estado IN ['RECIBIDO', 'EN_TRAMITE']
      AND d.fecha_recepcion IS NOT NULL
      AND d.fecha_recepcion < date() - duration({days: $dias_limite})
    RETURN d ORDER BY d.fecha_recepcion ASC
    """
    with drv.session() as session:
        result = session.run(query, dias_limite=dias_limite)
        return to_plain([dict(record["d"]) for record in result])


@app.get("/consultas/ultimo-correlativo")
async def get_ultimo_correlativo(
    oficina: str = Query(...), 
    tipo_documento: str = Query(...), 
    drv: Driver = Depends(get_driver)
):
    query = """
    MATCH (d:Documento)
    WHERE d.oficina_origen_sigla = $oficina
      AND d.tipo_documento = $tipo_documento
    RETURN d.correlativo, d.fecha_documento
    ORDER BY d.fecha_documento DESC, d.created_at DESC
    LIMIT 1
    """
    with drv.session() as session:
        result = session.run(query, oficina=oficina, tipo_documento=tipo_documento)
        record = result.single()
        if record:
            return {"correlativo": record["d.correlativo"], "fecha": str(record["d.fecha_documento"])}
        return {"correlativo": None, "fecha": None}


@app.get("/consultas/por-oficina")
async def get_por_oficina(
    oficina: str = Query(...),
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    drv: Driver = Depends(get_driver)
):
    # OJO con la precedencia: el OR de oficinas debe ir entre parentesis,
    # si no AND ate el filtro de fecha solo a la rama "destino" y los
    # documentos con ORIGEN en la oficina ignoran el mes/anio.
    where = "(d.oficina_origen_sigla = $oficina OR d.oficina_destino_sigla = $oficina)"
    params = {"oficina": oficina}

    if mes and anio:
        where += " AND d.fecha_documento >= date($inicio) AND d.fecha_documento <= date($fin)"
        import calendar
        params["inicio"] = f"{anio}-{mes:02d}-01"
        last_day = calendar.monthrange(anio, mes)[1]
        params["fin"] = f"{anio}-{mes:02d}-{last_day}"
    
    query = f"""
    MATCH (d:Documento)
    WHERE {where}
    RETURN d ORDER BY d.fecha_documento DESC LIMIT 100
    """
    
    with drv.session() as session:
        result = session.run(query, **params)
        return to_plain([dict(record["d"]) for record in result])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)