"""
Backend FastAPI Application
Main entry point for the Office Secretary Document Agent API.
"""
from contextlib import asynccontextmanager
from typing import Optional, Dict
import os
import logging
import httpx

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog
from app.services.vision_ocr import get_vision_processor

# Configurar structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Configure standard logging to DEBUG level
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)

# Variables de entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase-kong:8000")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
GRAPHIFY_URL = os.getenv("GRAPHIFY_URL", "http://graphify:8080")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.18.0.11:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "llava:latest")

# Cliente HTTP global para Supabase (PostgREST via Kong)
supabase_http_client: Optional[httpx.AsyncClient] = None
graphify_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""
    global graphify_client, supabase_http_client

    logger.info("starting_application", environment=ENVIRONMENT)

    # Inicializar cliente HTTP para Supabase (PostgREST via Kong)
    try:
        supabase_http_client = httpx.AsyncClient(
            base_url=SUPABASE_URL,
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        logger.info("supabase_http_client_initialized")
    except Exception as e:
        logger.error("supabase_http_client_failed", error=str(e))

    # Verificar Graphify
    try:
        graphify_client = httpx.AsyncClient(
            base_url=GRAPHIFY_URL,
            timeout=5.0,
        )
        resp = await graphify_client.get("/health")
        if resp.status_code == 200:
            logger.info("graphify_connected")
        else:
            logger.warning("graphify_unhealthy", status=resp.status_code)
    except Exception as e:
        logger.warning("graphify_connection_failed", error=str(e))

    # Verificar Ollama
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                if VISION_MODEL in model_names:
                    logger.info("vision_model_available", model=VISION_MODEL)
                else:
                    logger.warning("vision_model_not_found", model=VISION_MODEL, available=model_names)
            else:
                logger.warning("ollama_unhealthy", status=resp.status_code)
    except Exception as e:
        logger.warning("ollama_connection_failed", error=str(e))

    yield

    # Cleanup
    if supabase_http_client:
        await supabase_http_client.aclose()
    if graphify_client:
        await graphify_client.aclose()

    logger.info("shutting_down_application")


app = FastAPI(
    title="Office Secretary Document Agent API",
    description="API para gestión documental y consultas de secretaría",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if ENVIRONMENT == "development" else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ENVIRONMENT == "development" else ["https://docs.corposcentro.local"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with structlog."""
    start_time = structlog.processors.TimeStamper(fmt="iso")
    logger.info(
        "request_started",
        method=request.method,
        url=str(request.url),
        client=request.client.host if request.client else None,
    )

    response = await call_next(request)

    logger.info(
        "request_completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
    )
    return response


# ─────────────────────────────────────────────────────────────────
# DEPENDENCIAS
# ─────────────────────────────────────────────────────────────────

async def get_supabase_client() -> httpx.AsyncClient:
    if supabase_http_client is None:
        raise HTTPException(status_code=503, detail="Supabase no disponible")
    return supabase_http_client


async def get_graphify_client() -> httpx.AsyncClient:
    if graphify_client is None:
        raise HTTPException(status_code=503, detail="Graphify no disponible")
    return graphify_client


# ─────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str = "1.0.0"
    supabase: str
    graphify: str
    ollama: str


class DocumentoCreate(BaseModel):
    correlativo: str
    tipo_doc_codigo: str
    oficina_origen_sigla: str
    oficina_destino_sigla: str
    fecha_documento: str
    fecha_recepcion: Optional[str] = None
    remitente_id: Optional[str] = None
    destinatario_id: Optional[str] = None
    remitente: Optional[str] = None
    destinatario: Optional[str] = None
    asunto: Optional[str] = None
    folios: Optional[int] = None
    anexos: list = []
    estado: str = "RECIBIDO"
    prioridad: str = "NORMAL"
    observaciones: Optional[str] = None
    confianza_ocr: Optional[float] = None


class DocumentoResponse(DocumentoCreate):
    id: str
    creado_en: str
    actualizado_en: Optional[str] = None


# ─────────────────────────────────────────────────────────────────
# MODELOS - OFICINAS Y TIPOS DOCUMENTO
# ─────────────────────────────────────────────────────────────────

class OficinaCreate(BaseModel):
    sigla: str
    nombre: str
    activa: bool = True


class OficinaResponse(OficinaCreate):
    sigla: str
    nombre: str
    activa: bool


class TipoDocumentoCreate(BaseModel):
    codigo: str
    nombre: str
    prefijo_correlativo: str
    regla_secuencial: dict
    plazo_dias_respuesta: int
    requiere_anexos: bool


class TipoDocumentoResponse(TipoDocumentoCreate):
    codigo: str
    nombre: str
    prefijo_correlativo: str
    regla_secuencial: dict
    plazo_dias_respuesta: int
    requiere_anexos: bool


class VisionRequest(BaseModel):
    file_path: str
    mime_type: str


class VisionResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    confidence: Optional[float] = None


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - HEALTH
# ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    # Verificar Supabase
    supabase_status = "disconnected"
    if supabase_http_client:
        try:
            resp = await supabase_http_client.get("/rest/v1/documentos?select=id&limit=1")
            if resp.status_code == 200:
                supabase_status = "connected"
        except:
            pass

    # Verificar Graphify
    graphify_status = "disconnected"
    try:
        resp = await graphify_client.get("/health")
        if resp.status_code == 200:
            graphify_status = "connected"
    except:
        pass

    # Verificar Ollama
    ollama_status = "disconnected"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            if resp.status_code == 200:
                ollama_status = "connected"
    except:
        pass

    return HealthResponse(
        status="healthy" if all(s == "connected" for s in [supabase_status, graphify_status, ollama_status]) else "degraded",
        environment=ENVIRONMENT,
        supabase=supabase_status,
        graphify=graphify_status,
        ollama=ollama_status,
    )


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - DOCUMENTOS
# ─────────────────────────────────────────────────────────────────

@app.post("/api/documentos", response_model=DocumentoResponse, status_code=201)
async def create_documento(doc: DocumentoCreate, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Crear documento en Supabase e indexar en Graphify."""
    import uuid
    from datetime import datetime

    # Verificar si ya existe el correlativo
    check_result = await client.get(f"/rest/v1/documentos?correlativo=eq.{doc.correlativo}&select=id")
    if check_result.status_code == 200 and check_result.json():
        existing = check_result.json()[0]
        raise HTTPException(status_code=409, detail=f"El documento con correlativo '{doc.correlativo}' ya existe (ID: {existing['id']})")

    doc_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    data = doc.model_dump()
    data.update({
        "id": doc_id,
        "creado_en": now,
        "actualizado_en": now,
    })

    try:
        result = await client.post(
            "/rest/v1/documentos", 
            json=data,
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        created = result.json()
        
        # Indexar en Graphify (async, no bloquear)
        try:
            if graphify_client:
                # Graphify espera el esquema viejo (tipo_documento, oficina_origen):
                # se traduce desde el esquema actual (tipo_doc_codigo, *_sigla)
                graphify_payload = {
                    "id": doc_id,
                    "correlativo": data["correlativo"],
                    "tipo_documento": data["tipo_doc_codigo"],
                    "oficina_origen": data["oficina_origen_sigla"],
                    "oficina_destino": data["oficina_destino_sigla"],
                    "fecha_documento": data["fecha_documento"],
                    "fecha_recepcion": data.get("fecha_recepcion"),
                    "remitente": data.get("remitente"),
                    "destinatario": data.get("destinatario"),
                    "asunto": data.get("asunto"),
                    "folios": data.get("folios"),
                    "anexos": data.get("anexos") or [],
                    "estado": data.get("estado", "RECIBIDO"),
                    "prioridad": data.get("prioridad", "NORMAL"),
                    "observaciones": data.get("observaciones"),
                    "confianza_ocr": data.get("confianza_ocr"),
                }
                await graphify_client.post("/documentos", json=graphify_payload, timeout=10)
        except Exception as e:
            logger.warning("graphify_index_failed", error=str(e), doc_id=doc_id)

        return DocumentoResponse(**created[0])
    except httpx.HTTPStatusError as e:
        logger.error("create_documento_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error insertando documento: {e.response.text}")
    except Exception as e:
        logger.error("create_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - MÉTRICAS DASHBOARD (DEBE IR ANTES DE /api/documentos/{doc_id})
# ─────────────────────────────────────────────────────────────────

@app.get("/api/documentos/metricas")
async def get_metricas(
    oficina_origen: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Obtener métricas para el dashboard."""
    try:
        # Construir parámetros base
        params = [
            ("select", "estado,fecha_documento,oficina_origen_sigla,tipo_doc_codigo")
        ]
        
        # Filtros
        if oficina_origen:
            params.append(("oficina_origen_sigla", f"eq.{oficina_origen}"))
        if tipo_documento:
            params.append(("tipo_doc_codigo", f"eq.{tipo_documento}"))
        if fecha_desde and fecha_hasta:
            # Ambos: usar dos parámetros separados (PostgREST los trata como AND)
            params.append(("fecha_documento", f"gte.{fecha_desde}"))
            params.append(("fecha_documento", f"lte.{fecha_hasta}"))
        elif fecha_desde:
            params.append(("fecha_documento", f"gte.{fecha_desde}"))
        elif fecha_hasta:
            params.append(("fecha_documento", f"lte.{fecha_hasta}"))
        
        # Obtener todos los documentos para calcular métricas
        result = await client.get("/rest/v1/documentos", params=params)
        result.raise_for_status()
        docs = result.json()
        
        # Calcular métricas
        total = len(docs)
        
        # Por estado
        por_estado = {}
        for doc in docs:
            estado = doc.get("estado", "DESCONOCIDO")
            por_estado[estado] = por_estado.get(estado, 0) + 1
        
        por_estado_list = [
            {"estado": k, "count": v} 
            for k, v in sorted(por_estado.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Por oficina origen
        por_oficina = {}
        for doc in docs:
            oficina = doc.get("oficina_origen_sigla", "SIN_OFICINA")
            por_oficina[oficina] = por_oficina.get(oficina, 0) + 1
        
        por_oficina_list = [
            {"oficina": k, "count": v} 
            for k, v in sorted(por_oficina.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Este mes
        from datetime import datetime, date
        hoy = date.today()
        inicio_mes = date(hoy.year, hoy.month, 1).isoformat()
        
        # Crear params frescos para este mes (sin filtros de fecha previos)
        params_mes = {"select": "id"}
        if oficina_origen:
            params_mes["oficina_origen_sigla"] = f"eq.{oficina_origen}"
        if tipo_documento:
            params_mes["tipo_doc_codigo"] = f"eq.{tipo_documento}"
        params_mes["fecha_documento"] = f"gte.{inicio_mes}"
        
        result_mes = await client.get("/rest/v1/documentos", params=params_mes)
        result_mes.raise_for_status()
        docs_mes = result_mes.json()
        este_mes = len(docs_mes)
        
        # Oficinas activas (count de oficinas con documentos)
        oficinas_activas = len(por_oficina)
        
        return {
            "total": total,
            "este_mes": este_mes,
            "por_estado": por_estado_list,
            "por_oficina_origen": por_oficina_list,
            "oficinas_activas": oficinas_activas,
            "tendencia_total": 0,
            "tendencia_mes": 0,
            "tendencia_pendientes": 0,
        }
    except httpx.HTTPStatusError as e:
        logger.error("get_metricas_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error obteniendo métricas: {e.response.text}")
    except Exception as e:
        logger.error("get_metricas_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documentos/{doc_id}", response_model=DocumentoResponse)
async def get_documento(doc_id: str, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Obtener documento por ID."""
    try:
        result = await client.get(f"/rest/v1/documentos?id=eq.{doc_id}")
        result.raise_for_status()
        data = result.json()
        if data:
            return DocumentoResponse(**data[0])
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    except httpx.HTTPStatusError as e:
        logger.error("get_documento_failed", error=str(e), doc_id=doc_id)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("get_documento_failed", error=str(e), doc_id=doc_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documentos", response_model=list[DocumentoResponse])
async def list_documentos(
    search: Optional[str] = None,
    oficina_origen: Optional[str] = None,
    oficina_destino: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    estado: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Listar documentos con filtros."""
    try:
        # Usar lista de tuplas para permitir parámetros duplicados (AND implícito en PostgREST)
        params = [
            ("select", "*"),
            ("order", "fecha_documento.desc"),
            ("limit", str(limit)),
            ("offset", str(offset)),
        ]
        
        if search:
            # Busqueda sin acentos sobre search_text (columna generada con unaccent)
            # Se normaliza el termino en Python (NFD + quitar marcas) para que
            # "toner" encuentre "tóner", "informe" a "informé", etc.
            import unicodedata
            normalized = unicodedata.normalize("NFD", search)
            term = "".join(ch for ch in normalized if not unicodedata.combining(ch))
            # '*' es el wildcard de PostgREST; ',()/' son parte de su sintaxis -> se retiran
            term = "".join(ch for ch in term if ch not in ",()/").strip()
            if term:
                like = f"*{term}*"
                params.append(("search_text", f"ilike.{like}"))

        if oficina_origen:
            params.append(("oficina_origen_sigla", f"eq.{oficina_origen}"))
        if oficina_destino:
            params.append(("oficina_destino_sigla", f"eq.{oficina_destino}"))
        if tipo_documento:
            params.append(("tipo_doc_codigo", f"eq.{tipo_documento}"))
        if estado:
            params.append(("estado", f"eq.{estado}"))
        if fecha_desde and fecha_hasta:
            # Ambos: usar dos parámetros separados (PostgREST los trata como AND)
            params.append(("fecha_documento", f"gte.{fecha_desde}"))
            params.append(("fecha_documento", f"lte.{fecha_hasta}"))
        elif fecha_desde:
            params.append(("fecha_documento", f"gte.{fecha_desde}"))
        elif fecha_hasta:
            params.append(("fecha_documento", f"lte.{fecha_hasta}"))
        
        result = await client.get("/rest/v1/documentos", params=params)
        result.raise_for_status()
        data = result.json()
        return [DocumentoResponse(**doc) for doc in data]
    except httpx.HTTPStatusError as e:
        logger.error("list_documentos_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("list_documentos_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/documentos/{doc_id}", response_model=DocumentoResponse)
async def update_documento(doc_id: str, doc: DocumentoCreate, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Actualizar documento."""
    from datetime import datetime

    data = doc.model_dump()
    
    # Convertir strings vacíos a null para campos opcionales
    empty_to_null_fields = [
        "fecha_recepcion", "remitente_id", "destinatario_id",
        "remitente", "destinatario", "asunto", "observaciones"
    ]
    for field in empty_to_null_fields:
        if data.get(field) == "":
            data[field] = None
    
    # folios: 0 debe ser null (constraint CHECK folios > 0 OR NULL)
    if data.get("folios") == 0:
        data["folios"] = None
    
    data["actualizado_en"] = datetime.utcnow().isoformat()

    try:
        result = await client.patch(
            f"/rest/v1/documentos?id=eq.{doc_id}", 
            json=data,
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        data = result.json()
        if data:
            return DocumentoResponse(**data[0])
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    except httpx.HTTPStatusError as e:
        logger.error("update_documento_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error actualizando documento: {e.response.text}")
    except Exception as e:
        logger.error("update_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documentos/{doc_id}")
async def delete_documento(doc_id: str, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Eliminar documento: si está ARCHIVADO -> borrado permanente, sino -> marcar como ARCHIVADO."""
    from datetime import datetime

    try:
        # Primero verificar el estado actual del documento
        check_result = await client.get(f"/rest/v1/documentos?id=eq.{doc_id}&select=estado")
        check_result.raise_for_status()
        existing = check_result.json()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        current_estado = existing[0].get("estado", "")
        
        if current_estado == "ARCHIVADO":
            # BORRADO PERMANENTE (hard delete)
            result = await client.delete(
                f"/rest/v1/documentos?id=eq.{doc_id}",
                headers={"Prefer": "return=representation"}
            )
            result.raise_for_status()
            # PostgREST returns 200 with empty array if not found, check if actually deleted
            deleted = result.json()
            if not deleted:
                raise HTTPException(status_code=404, detail="Documento no encontrado")
            return {"message": "Documento eliminado permanentemente", "id": doc_id}
        else:
            # SOFT DELETE - marcar como ARCHIVADO
            result = await client.patch(
                f"/rest/v1/documentos?id=eq.{doc_id}",
                json={
                    "estado": "ARCHIVADO",
                    "actualizado_en": datetime.utcnow().isoformat()
                },
                headers={"Prefer": "return=representation"}
            )
            result.raise_for_status()
            if result.json():
                return {"message": "Documento archivado", "id": doc_id}
            raise HTTPException(status_code=404, detail="Documento no encontrado")
            
    except httpx.HTTPStatusError as e:
        logger.error("delete_documento_failed", error=str(e), response=e.response.text, doc_id=doc_id)
        # Si el error original es 404, propagar como 404
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        raise HTTPException(status_code=500, detail=f"Error eliminando documento: {e.response.text}")
    except Exception as e:
        # No capturar HTTPException, dejar que se propague
        if isinstance(e, HTTPException):
            raise
        logger.error("delete_documento_failed", error=str(e), doc_id=doc_id)
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - VISION/OCR
# ─────────────────────────────────────────────────────────────────

@app.post("/api/vision/extract", response_model=VisionResponse)
async def extract_vision(request: VisionRequest):
    """Extraer datos de imagen/PDF usando Vision API (Ollama o NVIDIA)."""
    try:
        # Usar factory para obtener el procesador apropiado
        processor = get_vision_processor()
        result = await processor.extract_document_data(request.file_path, request.mime_type)
        
        return VisionResponse(
            success=result["success"],
            data=result.get("data"),
            error=result.get("error"),
            confidence=result.get("confidence", 0.0)
        )
    except Exception as e:
        logger.error("vision_extract_failed", error=str(e))
        return VisionResponse(success=False, error=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - CONSULTAS GRAPHIFY
# ─────────────────────────────────────────────────────────────────

@app.get("/api/consultas/trace/{correlativo}")
async def trace_documento(correlativo: str, graphify: httpx.AsyncClient = Depends(get_graphify_client)):
    """Trazabilidad completa vía Graphify."""
    try:
        resp = await graphify.get(f"/trace/{correlativo}")
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Documento no encontrado en grafo")
        else:
            raise HTTPException(status_code=500, detail="Error en Graphify")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("trace_failed", error=str(e), correlativo=correlativo)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/consultas/pendientes")
async def get_pendientes(dias_limite: int = 5, graphify: httpx.AsyncClient = Depends(get_graphify_client)):
    """Documentos pendientes de respuesta."""
    try:
        resp = await graphify.get("/consultas/pendientes", params={"dias_limite": dias_limite})
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=500, detail="Error en Graphify")
    except Exception as e:
        logger.error("pendientes_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/consultas/buscar")
async def buscar_documentos(q: str, graphify: httpx.AsyncClient = Depends(get_graphify_client)):
    """Buscar documentos en Graphify."""
    try:
        resp = await graphify.get(f"/buscar?q={q}&limit=10")
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=500, detail="Error en Graphify")
    except Exception as e:
        logger.error("buscar_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/consultas/ultimo-correlativo")
async def ultimo_correlativo(
    oficina: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    graphify: httpx.AsyncClient = Depends(get_graphify_client),
):
    """Ultimo correlativo por oficina y tipo (via Graphify)."""
    try:
        params: Dict[str, str] = {}
        if oficina:
            params["oficina"] = oficina
        if tipo_documento:
            params["tipo_documento"] = tipo_documento
        resp = await graphify.get("/consultas/ultimo-correlativo", params=params)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="No hay documentos en el grafo")
        raise HTTPException(status_code=500, detail="Error en Graphify")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ultimo_correlativo_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/consultas/por-oficina")
async def por_oficina(
    oficina: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    limit: int = 50,
    graphify: httpx.AsyncClient = Depends(get_graphify_client),
):
    """Documentos por oficina (via Graphify)."""
    try:
        params: Dict[str, str | int] = {"limit": limit}
        if oficina:
            params["oficina"] = oficina
        if tipo_documento:
            params["tipo_documento"] = tipo_documento
        if mes:
            params["mes"] = mes
        if anio:
            params["anio"] = anio
        resp = await graphify.get("/consultas/por-oficina", params=params)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=500, detail="Error en Graphify")
    except Exception as e:
        logger.error("por_oficina_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - OFICINAS
# ─────────────────────────────────────────────────────────────────

@app.get("/api/oficinas", response_model=list[OficinaResponse])
async def list_oficinas(activas: Optional[bool] = None, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Listar oficinas."""
    try:
        params = {"select": "*", "order": "sigla"}
        if activas is not None:
            params["activa"] = f"eq.{str(activas).lower()}"
        result = await client.get("/rest/v1/oficinas", params=params)
        result.raise_for_status()
        return result.json()
    except httpx.HTTPStatusError as e:
        logger.error("list_oficinas_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("list_oficinas_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/oficinas", response_model=OficinaResponse, status_code=201)
async def create_oficina(oficina: OficinaCreate, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Crear oficina."""
    try:
        # Verificar si ya existe
        check_result = await client.get(f"/rest/v1/oficinas?sigla=eq.{oficina.sigla}&select=sigla")
        if check_result.status_code == 200 and check_result.json():
            raise HTTPException(status_code=409, detail=f"La oficina con sigla '{oficina.sigla}' ya existe")
        
        data = oficina.model_dump()
        # Agregar timestamps requeridos
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        data["creada_en"] = now
        data["actualizada_en"] = now
        
        result = await client.post(
            "/rest/v1/oficinas",
            json=data,
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        return OficinaResponse(**result.json()[0])
    except httpx.HTTPStatusError as e:
        logger.error("create_oficina_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error creando oficina: {e.response.text}")
    except Exception as e:
        logger.error("create_oficina_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/oficinas/{sigla}", response_model=OficinaResponse)
async def update_oficina(sigla: str, oficina: OficinaCreate, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Actualizar oficina."""
    try:
        data = oficina.model_dump()
        # Agregar timestamp de actualización
        from datetime import datetime
        data["actualizada_en"] = datetime.utcnow().isoformat()
        
        result = await client.patch(
            f"/rest/v1/oficinas?sigla=eq.{sigla}",
            json=data,
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        data = result.json()
        if data:
            return OficinaResponse(**data[0])
        raise HTTPException(status_code=404, detail="Oficina no encontrada")
    except httpx.HTTPStatusError as e:
        logger.error("update_oficina_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error actualizando oficina: {e.response.text}")
    except Exception as e:
        logger.error("update_oficina_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/oficinas/{sigla}")
async def delete_oficina(sigla: str, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Eliminar oficina (soft delete - marcar inactiva)."""
    try:
        result = await client.patch(
            f"/rest/v1/oficinas?sigla=eq.{sigla}",
            json={"activa": False},
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        if result.json():
            return {"message": "Oficina desactivada", "sigla": sigla}
        raise HTTPException(status_code=404, detail="Oficina no encontrada")
    except httpx.HTTPStatusError as e:
        logger.error("delete_oficina_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error eliminando oficina: {e.response.text}")
    except Exception as e:
        logger.error("delete_oficina_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - TIPOS DOCUMENTO
# ─────────────────────────────────────────────────────────────────

@app.get("/api/tipos-documento", response_model=list[TipoDocumentoResponse])
async def list_tipos_documento(client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Listar tipos de documento."""
    try:
        result = await client.get("/rest/v1/tipos_documento", params={"select": "*", "order": "codigo"})
        result.raise_for_status()
        return result.json()
    except httpx.HTTPStatusError as e:
        logger.error("list_tipos_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("list_tipos_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tipos-documento", response_model=TipoDocumentoResponse, status_code=201)
async def create_tipo_documento(tipo: TipoDocumentoCreate, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Crear tipo de documento."""
    try:
        # Verificar si ya existe
        check_result = await client.get(f"/rest/v1/tipos_documento?codigo=eq.{tipo.codigo}&select=codigo")
        if check_result.status_code == 200 and check_result.json():
            raise HTTPException(status_code=409, detail=f"El tipo de documento con código '{tipo.codigo}' ya existe")
        
        data = tipo.model_dump()
        result = await client.post(
            "/rest/v1/tipos_documento",
            json=data,
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        return TipoDocumentoResponse(**result.json()[0])
    except httpx.HTTPStatusError as e:
        logger.error("create_tipo_documento_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error creando tipo documento: {e.response.text}")
    except Exception as e:
        logger.error("create_tipo_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/tipos-documento/{codigo}", response_model=TipoDocumentoResponse)
async def update_tipo_documento(codigo: str, tipo: TipoDocumentoCreate, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Actualizar tipo de documento."""
    try:
        data = tipo.model_dump()
        result = await client.patch(
            f"/rest/v1/tipos_documento?codigo=eq.{codigo}",
            json=data,
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        data = result.json()
        if data:
            return TipoDocumentoResponse(**data[0])
        raise HTTPException(status_code=404, detail="Tipo de documento no encontrado")
    except httpx.HTTPStatusError as e:
        logger.error("update_tipo_documento_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error actualizando tipo documento: {e.response.text}")
    except Exception as e:
        logger.error("update_tipo_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/tipos-documento/{codigo}")
async def delete_tipo_documento(codigo: str, client: httpx.AsyncClient = Depends(get_supabase_client)):
    """Eliminar tipo de documento."""
    try:
        result = await client.delete(
            f"/rest/v1/tipos_documento?codigo=eq.{codigo}",
            headers={"Prefer": "return=representation"}
        )
        result.raise_for_status()
        if result.json():
            return {"message": "Tipo de documento eliminado", "codigo": codigo}
        raise HTTPException(status_code=404, detail="Tipo de documento no encontrado")
    except httpx.HTTPStatusError as e:
        logger.error("delete_tipo_documento_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error eliminando tipo documento: {e.response.text}")
    except Exception as e:
        logger.error("delete_tipo_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)