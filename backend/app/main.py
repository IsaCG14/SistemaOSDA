"""
Backend FastAPI Application
Main entry point for the Office Secretary Document Agent API.
"""
from contextlib import asynccontextmanager
from typing import Optional, Dict
from datetime import datetime
import os
import logging
import httpx
import psycopg

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
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "llava:latest")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")

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
    allow_origins=[
        "http://localhost",
        "http://localhost:5173",
        "http://127.0.0.1",
        "http://127.0.0.1:5173",
        "http://192.168.251.203",
        "http://corpocentro.osda.net",
    ] if ENVIRONMENT == "development" else ["https://docs.corposcentro.local"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
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


async def get_user_office(request: Request) -> Optional[str]:
    """
    Retorna oficina_sigla del usuario autenticado.
    None si es ADMIN (ve todo).
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    
    token = auth.split(" ", 1)[1].strip()
    try:
        from jose import jwt as jose_jwt
        from app.core.config import settings
        payload = jose_jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        user_email = payload.get("email")
        # El rol ADMIN está en user_metadata.role (no en el claim 'role' estándar de JWT)
        user_role = payload.get("user_metadata", {}).get("role") or payload.get("role")
        
        # ADMIN ve todo
        if user_role == "ADMIN":
            return None
        
        if user_email:
            # Buscar persona por email -> oficina_sigla
            client = supabase_http_client
            if client:
                result = await client.get(f"/rest/v1/personas?email=eq.{user_email}&select=oficina_sigla")
                if result.status_code == 200 and result.json():
                    return result.json()[0]["oficina_sigla"]
    except Exception:
        pass
    return None


async def get_user_office_and_role(request: Request) -> tuple[Optional[str], Optional[str]]:
    """
    Retorna (oficina_sigla, role) del usuario autenticado.
    oficina_sigla = None si es ADMIN.
    role = 'ADMIN' | 'SECRETARIO' | None
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return (None, None)
    
    token = auth.split(" ", 1)[1].strip()
    try:
        from jose import jwt as jose_jwt
        from app.core.config import settings
        payload = jose_jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        user_email = payload.get("email")
        user_role = payload.get("user_metadata", {}).get("role") or payload.get("role")
        
        # ADMIN ve todo
        if user_role == "ADMIN":
            return (None, "ADMIN")
        
        if user_email:
            client = supabase_http_client
            if client:
                result = await client.get(f"/rest/v1/personas?email=eq.{user_email}&select=oficina_sigla")
                if result.status_code == 200 and result.json():
                    oficina = result.json()[0]["oficina_sigla"]
                    return (oficina, user_role or "SECRETARIO")
    except Exception:
        pass
    return (None, None)


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
    creado_por: Optional[str] = None


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
async def create_documento(
    doc: DocumentoCreate, 
    request: Request, 
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Crear documento en Supabase e indexar en Graphify.
    
    Para SECRETARIO: oficina_origen_sigla se fuerza a su oficina.
    Para ADMIN: respeta lo enviado en el payload.
    """
    import uuid
    from datetime import datetime
    
    user_office, user_role = user_info
    
    # Obtener usuario autenticado (creado_por)
    creado_por = None
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            from jose import jwt as jose_jwt, JWTError
            from app.core.config import settings
            payload = jose_jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
            user_email = payload.get("email")
            if user_email:
                persona_result = await client.get(f"/rest/v1/personas?email=eq.{user_email}&select=id")
                if persona_result.status_code == 200 and persona_result.json():
                    creado_por = persona_result.json()[0]["id"]
        except Exception:
            pass

    # Si viene telegram_user_id del bot, usarlo para buscar persona
    telegram_user_id = doc.model_dump().get("telegram_user_id")
    if telegram_user_id and not creado_por:
        persona_result = await client.get(f"/rest/v1/personas?telegram_user_id=eq.{telegram_user_id}&select=id")
        if persona_result.status_code == 200 and persona_result.json():
            creado_por = persona_result.json()[0]["id"]

    # Validar y forzar oficina_origen según rol
    if user_role == "ADMIN":
        # ADMIN: respeta lo enviado en el payload
        pass
    else:
        # SECRETARIO: forzar oficina_origen_sigla a su oficina
        if not user_office:
            raise HTTPException(status_code=403, detail="Usuario sin oficina asignada")
        doc.oficina_origen_sigla = user_office

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
        "creado_por": creado_por,
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
    request: Request,
    oficina_origen: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    user_office: Optional[str] = Depends(get_user_office),
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Obtener métricas para el dashboard. Filtrado automático por oficina del usuario (SECRETARIO)."""
    try:
        # Construir parámetros base
        params = [
            ("select", "estado,fecha_documento,oficina_origen_sigla,tipo_doc_codigo,eliminado_en"),
        ]
        
        # Filtrado automático por oficina del usuario (SECRETARIO)
        if user_office:
            # Filtrar: origen = user_office OR destino = user_office
            params.append(("or", f"(oficina_origen_sigla.eq.{user_office},oficina_destino_sigla.eq.{user_office})"))
        else:
            # ADMIN: aplicar filtros manuales si se proporcionaron
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
        
        # EXCLUIR documentos eliminados (soft delete)
        params.append(("eliminado_en", "is.null"))
        
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
        params_mes = [("select", "id")]
        
        if user_office:
            params_mes.append(("or", f"(oficina_origen_sigla.eq.{user_office},oficina_destino_sigla.eq.{user_office})"))
        elif oficina_origen:
            params_mes.append(("oficina_origen_sigla", f"eq.{oficina_origen}"))
        
        if tipo_documento:
            params_mes.append(("tipo_doc_codigo", f"eq.{tipo_documento}"))
        
        params_mes.append(("fecha_documento", f"gte.{inicio_mes}"))
        # EXCLUIR documentos eliminados (soft delete)
        params_mes.append(("eliminado_en", "is.null"))
        
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
async def get_documento(
    doc_id: str, 
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Obtener documento por ID. Verifica acceso por oficina."""
    user_office, user_role = user_info
    
    try:
        result = await client.get(f"/rest/v1/documentos?id=eq.{doc_id}")
        result.raise_for_status()
        data = result.json()
        if not data:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        doc = data[0]
        
        # Verificar acceso: ADMIN ve todo, SECRETARIO solo su oficina (origen OR destino)
        if user_role != "ADMIN":
            user_office = None
            auth = request.headers.get("authorization") or request.headers.get("Authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1].strip()
                try:
                    from jose import jwt as jose_jwt
                    from app.core.config import settings
                    payload = jose_jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
                    user_email = payload.get("email")
                    if user_email:
                        client_local = supabase_http_client
                        if client_local:
                            result = await client_local.get(f"/rest/v1/personas?email=eq.{user_email}&select=oficina_sigla")
                            if result.status_code == 200 and result.json():
                                user_office = result.json()[0]["oficina_sigla"]
                except Exception:
                    pass
            
            if user_office:
                doc_oficina_origen = doc.get("oficina_origen_sigla")
                doc_oficina_destino = doc.get("oficina_destino_sigla")
                if doc_oficina_origen != user_office and doc_oficina_destino != user_office:
                    raise HTTPException(status_code=403, detail="No tiene acceso a este documento")
        
        return DocumentoResponse(**doc)
    except httpx.HTTPStatusError as e:
        logger.error("get_documento_failed", error=str(e), doc_id=doc_id)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("get_documento_failed", error=str(e), doc_id=doc_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documentos", response_model=list[DocumentoResponse])
async def list_documentos(
    request: Request,
    search: Optional[str] = None,
    oficina_origen: Optional[str] = None,
    oficina_destino: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    estado: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_office: Optional[str] = Depends(get_user_office),
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Listar documentos con filtros. Filtrado automático por oficina del usuario (SECRETARIO)."""
    try:
        # Usar lista de tuplas para permitir parámetros duplicados (AND implícito en PostgREST)
        params = [
            ("select", "*"),
            ("order", "fecha_documento.desc"),
            ("limit", str(limit)),
            ("offset", str(offset)),
        ]
        
        # Filtrado automático por oficina del usuario (SECRETARIO)
        # Si user_office existe (no es ADMIN), filtrar: origen = user_office OR destino = user_office
        if user_office:
            # PostgREST OR filter: (oficina_origen_sigla.eq.X,oficina_destino_sigla.eq.X)
            params.append(("or", f"(oficina_origen_sigla.eq.{user_office},oficina_destino_sigla.eq.{user_office})"))
        else:
            # ADMIN: aplicar filtros manuales si se proporcionaron
            if oficina_origen:
                params.append(("oficina_origen_sigla", f"eq.{oficina_origen}"))
            if oficina_destino:
                params.append(("oficina_destino_sigla", f"eq.{oficina_destino}"))
        
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
        
        # Para paginación: obtener total count (sin limit/offset)
        # Hacer query de count con los mismos filtros
        count_params = [p for p in params if p[0] not in ("limit", "offset", "select", "order")]
        count_params.append(("select", "count"))
        count_result = await client.get("/rest/v1/documentos", params=count_params)
        count_result.raise_for_status()
        # La respuesta con select=count devuelve [{"count": N}]
        try:
            total_count = count_result.json()[0]["count"]
        except (IndexError, KeyError, TypeError):
            total_count = 0

        result = await client.get("/rest/v1/documentos", params=params)
        result.raise_for_status()
        data = result.json()
        
        # Devolver headers con total count para paginación en frontend
        from fastapi import Response
        # No podemos usar Response directamente aquí, pero podemos usar headers en la respuesta
        # Mejor: usar un header personalizado
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=[DocumentoResponse(**doc).model_dump() for doc in data],
            headers={"X-Total-Count": str(total_count)}
        )
    except httpx.HTTPStatusError as e:
        logger.error("list_documentos_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("list_documentos_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/documentos/{doc_id}", response_model=DocumentoResponse)
async def update_documento(
    doc_id: str, 
    doc: DocumentoCreate, 
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Actualizar documento. Verifica acceso por oficina."""
    user_office, user_role = user_info
    
    # Verificar acceso primero
    check_result = await client.get(f"/rest/v1/documentos?id=eq.{doc_id}&select=oficina_origen_sigla,oficina_destino_sigla")
    check_result.raise_for_status()
    existing = check_result.json()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Verificar acceso
    if user_role != "ADMIN":
        doc_oficina_origen = existing[0].get("oficina_origen_sigla")
        doc_oficina_destino = existing[0].get("oficina_destino_sigla")
        if user_office not in (doc_oficina_origen, doc_oficina_destino):
            raise HTTPException(status_code=403, detail="No tiene acceso a este documento")
        
        # SECRETARIO no puede cambiar oficina_origen
        if doc.oficina_origen_sigla != user_office:
            raise HTTPException(status_code=403, detail="No puede cambiar la oficina de origen")
    
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
async def delete_documento(
    doc_id: str, 
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_supabase_client)
):
    """Eliminar documento: si está ARCHIVADO -> borrado permanente, sino -> marcar como ARCHIVADO.
    Verifica acceso por oficina."""
    user_office, user_role = user_info
    
    from datetime import datetime
    
    try:
        # Primero verificar el estado actual del documento y oficina
        check_result = await client.get(f"/rest/v1/documentos?id=eq.{doc_id}&select=estado,oficina_origen_sigla,oficina_destino_sigla")
        check_result.raise_for_status()
        existing = check_result.json()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        # Verificar acceso
        if user_role != "ADMIN":
            doc_oficina_origen = existing[0].get("oficina_origen_sigla")
            doc_oficina_destino = existing[0].get("oficina_destino_sigla")
            if user_office not in (doc_oficina_origen, doc_oficina_destino):
                raise HTTPException(status_code=403, detail="No tiene acceso a este documento")
        
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
async def buscar_documentos(
    q: str, 
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
    graphify: httpx.AsyncClient = Depends(get_graphify_client)
):
    """Buscar documentos en Graphify. Filtrado automático por oficina."""
    user_office, user_role = user_info
    
    try:
        params = {"q": q, "limit": 10}
        if user_role != "ADMIN" and user_office:
            params["oficina"] = user_office
        
        resp = await graphify.get("/buscar", params=params)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=500, detail="Error en Graphify")
    except HTTPException:
        raise
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
# ENDPOINTS - USUARIOS (auth.users, lectura via psycopg directo)
# ─────────────────────────────────────────────────────────────────

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

class UsuarioCreate(BaseModel):
    email: str
    password: str
    role: str = "SECRETARIO"
    nombre: Optional[str] = None


class UsuarioUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    nombre: Optional[str] = None


def _caller_role(request: Request) -> Optional[str]:
    """Rol del usuario autenticado que hace la peticion (None si token invalido)."""
    from jose import jwt as jose_jwt, JWTError
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        # GoTrue firma con aud="" (vacio) y python-jose lo valida estrictamente:
        # se omite la validacion de audience; la FIRMA sigue verificada.
        payload = jose_jwt.decode(
            token, SUPABASE_JWT_SECRET, algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub or not SUPABASE_DB_PASSWORD:
        return None
    # El rol vive en raw_user_meta_data: se lee de la BD para no depender
    # de tokens viejos con roles desactualizados
    import psycopg
    try:
        conn = psycopg.connect(host="supabase-db", dbname="postgres", user="postgres",
                               password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("SELECT raw_user_meta_data->>'role' FROM auth.users WHERE id = %s", (sub,))
            fila = cur.fetchone()
        conn.close()
        return fila[0] if fila else None
    except Exception:
        return None


@app.get("/api/usuarios")
async def list_usuarios(request: Request):
    """Listar cuentas de login (auth.users) - SOLO LECTURA (solo ADMIN).

    Lee email, rol, nombre, estado y ultimo acceso desde el schema auth
    (no expuesto por PostgREST) via conexion directa a Postgres.
    No modifica nada.
    """
    # Solo ADMIN puede listar usuarios
    rol = _caller_role(request)
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede listar usuarios")

    import psycopg
    if not SUPABASE_DB_PASSWORD:
        raise HTTPException(status_code=500, detail="SUPABASE_DB_PASSWORD no configurada en el backend")
    try:
        conn = psycopg.connect(
            host="supabase-db",
            dbname="postgres",
            user="postgres",
            password=SUPABASE_DB_PASSWORD,
            port=5432,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.email,
                       coalesce(u.raw_user_meta_data->>'role', 'SECRETARIO') as role,
                       coalesce(u.raw_user_meta_data->>'nombre', '') as nombre,
                       (u.banned_until IS NULL) as activo,
                       coalesce(u.email_confirmed_at::text, '') as confirmado,
                       coalesce(u.last_sign_in_at::text, u.created_at::text) as ultimo_acceso,
                       u.created_at::text as creado
                FROM auth.users u
                ORDER BY u.created_at ASC
            """)
            filas = cur.fetchall()
        conn.close()
        return [
            {
                "email": f[0],
                "role": f[1],
                "nombre": f[2],
                "activo": f[3],
                "email_confirmado": bool(f[4]),
                "ultimo_acceso": f[5],
                "creado": f[6],
            }
            for f in filas
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_usuarios_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
        raise
    except Exception as e:
        logger.error("list_usuarios_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/usuarios", status_code=201)
async def create_usuario(nuevo: UsuarioCreate, request: Request):
    """Registrar un usuario nuevo (solo ADMIN).

    Crea la cuenta via GoTrue Admin API (nunca se insertan password
    hashes a mano). El rol queda en raw_user_meta_data.
    """
    import psycopg
    # 1. Solo ADMIN puede crear usuarios
    rol = _caller_role(request)
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede registrar usuarios")

    # 2. Validaciones
    email = nuevo.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Email inválido")
    if len(nuevo.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
    if nuevo.role not in ("ADMIN", "SECRETARIO"):
        raise HTTPException(status_code=400, detail="Rol inválido (ADMIN o SECRETARIO)")

    # 3. ¿Ya existe?
    try:
        conn = psycopg.connect(host="supabase-db", dbname="postgres", user="postgres",
                               password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM auth.users WHERE email = %s", (email,))
            if cur.fetchone():
                conn.close()
                raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_usuario_check_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # 4. Crear via GoTrue Admin API (hash de password correcto)
    try:
        admin_client = httpx.AsyncClient(timeout=15, trust_env=False)
        resp = await admin_client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "email": email,
                "password": nuevo.password,
                "email_confirm": True,
                "user_metadata": {
                    "role": nuevo.role,
                    **({"nombre": nuevo.nombre} if nuevo.nombre else {}),
                },
            },
        )
        await admin_client.aclose()
        if resp.status_code not in (200, 201):
            detail = "Error creando usuario en GoTrue"
            try:
                detail = resp.json().get("msg") or resp.json().get("message") or detail
            except Exception:
                pass
            logger.error("create_usuario_gotrue_failed", status=resp.status_code, body=resp.text[:300])
            raise HTTPException(status_code=resp.status_code, detail=detail)
        creado = resp.json()
        logger.info("usuario_creado", email=email, rol=nuevo.role)
        return {
            "email": creado.get("email", email),
            "role": nuevo.role,
            "activo": True,
            "email_confirmado": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_usuario_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/usuarios/{email}")
async def update_usuario(email: str, datos: UsuarioUpdate, request: Request):
    """Actualizar usuario (solo ADMIN). Permite cambiar contraseña, rol o nombre."""
    import psycopg
    import httpx

    # 1. Solo ADMIN puede actualizar usuarios
    rol = _caller_role(request)
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede actualizar usuarios")

    email = email.strip().lower()

    # 2. Verificar que existe
    try:
        conn = psycopg.connect(
            host="supabase-db",
            dbname="postgres",
            user="postgres",
            password=SUPABASE_DB_PASSWORD,
            port=5432,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM auth.users WHERE email = %s", (email,))
            user_row = cur.fetchone()
            if not user_row:
                conn.close()
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            user_id = user_row[0]
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_usuario_check_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    # 3. Actualizar via GoTrue Admin API
    try:
        admin_client = httpx.AsyncClient(timeout=15, trust_env=False)
        update_data = {}
        if datos.password:
            if len(datos.password) < 8:
                raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
            update_data["password"] = datos.password
        if datos.role:
            if datos.role not in ("ADMIN", "SECRETARIO"):
                raise HTTPException(status_code=400, detail="Rol inválido (ADMIN o SECRETARIO)")
            update_data["user_metadata"] = {"role": datos.role}
        if datos.nombre is not None:
            if "user_metadata" not in update_data:
                update_data["user_metadata"] = {}
            update_data["user_metadata"]["nombre"] = datos.nombre

        if not update_data:
            raise HTTPException(status_code=400, detail="No hay datos para actualizar")

        resp = await admin_client.put(
            f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
            json=update_data,
        )
        await admin_client.aclose()

        if resp.status_code not in (200, 201):
            detail = "Error actualizando usuario en GoTrue"
            try:
                detail = resp.json().get("msg") or resp.json().get("message") or detail
            except Exception:
                pass
            logger.error("update_usuario_gotrue_failed", status=resp.status_code, body=resp.text[:300])
            raise HTTPException(status_code=resp.status_code, detail=detail)

        actualizado = resp.json()
        logger.info("usuario_actualizado", email=email)
        return {
            "email": actualizado.get("email", email),
            "role": datos.role or actualizado.get("user_metadata", {}).get("role"),
            "nombre": datos.nombre or actualizado.get("user_metadata", {}).get("nombre"),
            "message": "Usuario actualizado correctamente",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_usuario_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - BACKUP (ejecutar scripts/backup.sh y listar respaldos)
# ─────────────────────────────────────────────────────────────────

BACKUP_DIR = os.getenv("BACKUP_DIR", "/backups")
BACKUP_SCRIPT = os.getenv("BACKUP_SCRIPT", "/scripts/backup.sh")
RESTORE_SCRIPT = os.getenv("RESTORE_SCRIPT", "/scripts/restore.sh")


@app.get("/api/backup/listar")
async def listar_backups(request: Request):
    """Listar respaldos existentes con tamaño y fecha (solo ADMIN)."""
    if _caller_role(request) != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede ver los respaldos")
    try:
        archivos = []
        for nombre in os.listdir(BACKUP_DIR):
            ruta = os.path.join(BACKUP_DIR, nombre)
            if os.path.isfile(ruta) and nombre != ".gitkeep":
                st = os.stat(ruta)
                archivos.append({
                    "nombre": nombre,
                    "tamano_bytes": st.st_size,
                    "fecha": datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z",
                })
        archivos.sort(key=lambda a: a["fecha"], reverse=True)
        return {"backups": archivos, "directorio": BACKUP_DIR}
    except FileNotFoundError:
        return {"backups": [], "directorio": BACKUP_DIR}
    except Exception as e:
        logger.error("listar_backups_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backup/ejecutar")
async def ejecutar_backup(request: Request):
    """Ejecutar backup AHORA (solo ADMIN). Corre el mismo script del cron.

    El endpoint responde cuando termina (el dump completo tarda segundos),
    con un resumen de lo generado.
    """
    import subprocess
    import asyncio as _asyncio
    if _caller_role(request) != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede ejecutar respaldos")
    if not os.path.exists(BACKUP_SCRIPT):
        raise HTTPException(status_code=500, detail="Script de backup no encontrado en el backend")
    try:
        antes = set(os.listdir(BACKUP_DIR)) if os.path.isdir(BACKUP_DIR) else set()
        # Ejecutar SIN bloquear el event loop de la API
        proc = await _asyncio.create_subprocess_exec(
            "bash", BACKUP_SCRIPT,
            stdout=_asyncio.subprocess.PIPE,
            stderr=_asyncio.subprocess.STDOUT,
        )
        try:
            salida, _ = await _asyncio.wait_for(proc.communicate(), timeout=300)
        except _asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(status_code=500, detail="El backup excedió 5 minutos; revisar logs/backup.log")
        if proc.returncode != 0:
            logger.error("backup_ejecutar_failed", rc=proc.returncode, salida=salida.decode()[-500:])
            raise HTTPException(status_code=500, detail="El backup falló; ver logs/backup.log")
        despues = set(os.listdir(BACKUP_DIR))
        nuevos = sorted(despues - antes)
        return {
            "ok": True,
            "generados": nuevos,
            "salida": salida.decode()[-2000:],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("backup_ejecutar_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backup/restaurar")
async def restaurar_backup(request: Request):
    """Restaurar base de datos desde un backup (solo ADMIN).

    Body JSON: { "archivo": "supabase_20261028_140406.sql.gz", "confirmar": "RESTAURAR" }

    Soporta dos formatos:
    - .sql.gz (dump plano): usa psql. NO limpia la BD antes (solo inserta).
    - .dump (custom): usa pg_restore --clean. LIMPIA y recrea la BD completamente (recomendado).
    """
    import asyncio as _asyncio
    if _caller_role(request) != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede restaurar respaldos")

    body = await request.json()
    archivo = body.get("archivo", "").strip()
    confirmar = body.get("confirmar", "").strip()

    if not archivo:
        raise HTTPException(status_code=400, detail="Falta 'archivo' en el body")
    if confirmar != "RESTAURAR":
        raise HTTPException(status_code=400, detail="Debe confirmar enviando 'confirmar': 'RESTAURAR'")

    ruta_archivo = os.path.join(BACKUP_DIR, archivo)
    if not os.path.isfile(ruta_archivo):
        raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {archivo}")

    es_dump_custom = archivo.endswith(".dump")
    es_sql_gz = archivo.endswith(".sql.gz")

    if not (es_dump_custom or es_sql_gz):
        raise HTTPException(status_code=400, detail="Formato no soportado. Use .sql.gz o .dump")

    # Servicios a detener/iniciar
    servicios = ["backend", "telegram-bot", "graphify", "migrator"]

    # Detectar si estamos en host (docker disponible) o contenedor
    import shutil
    docker_disponible = shutil.which("docker") is not None

    try:
        # 1. Detener servicios que usan la BD (evita conexiones activas durante restore)
        #    Solo si docker está disponible (entorno host)
        if docker_disponible:
            for s in servicios:
                proc = await _asyncio.create_subprocess_exec(
                    "docker", "compose", "stop", s,
                    stdout=_asyncio.subprocess.DEVNULL,
                    stderr=_asyncio.subprocess.DEVNULL,
                    cwd="/home/openclaw/office-secretary-document-agent"
                )
                await proc.wait()

        # 2. Ejecutar restauración según formato
        if es_dump_custom:
            # pg_restore --clean falla por SET transaction_timeout en el dump (PostgreSQL 17+)
            # Solución: extraer SQL del dump custom, filtrar SET problemáticos, y ejecutar con psql
            # Nota: stderr de pg_restore (warnings) no debe ir a psql, solo stdout (SQL)
            if docker_disponible:
                # Host: pg_restore a SQL limpio (stdout) -> psql en contenedor DB
                # stderr va a /dev/null para no contaminar el SQL
                restore_cmd = (
                    f"docker exec osda-supabase-db pg_restore -U postgres -d postgres "
                    f"--clean --if-exists --no-owner --no-privileges --no-tablespaces "
                    f"--no-security-labels --no-comments {ruta_archivo} 2>/dev/null | "
                    f"grep -v '^SET transaction_timeout' | "
                    f"docker exec -i osda-supabase-db psql -U postgres -d postgres"
                )
                proc = await _asyncio.create_subprocess_shell(
                    restore_cmd,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                    cwd="/home/openclaw/office-secretary-document-agent"
                )
            else:
                # Contenedor: pg_restore a SQL limpio (stdout) -> psql directo
                restore_cmd = (
                    f"PGPASSWORD=\"$SUPABASE_DB_PASSWORD\" pg_restore -h supabase-db -U postgres -d postgres "
                    f"--clean --if-exists --no-owner --no-privileges --no-tablespaces "
                    f"--no-security-labels --no-comments {ruta_archivo} 2>/dev/null | "
                    f"grep -v '^SET transaction_timeout' | "
                    f"PGPASSWORD=\"$SUPABASE_DB_PASSWORD\" psql -h supabase-db -U postgres -d postgres"
                )
                proc = await _asyncio.create_subprocess_shell(
                    restore_cmd,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                )
        else:
            # .sql.gz: psql (no limpia, solo inserta - puede fallar por duplicados)
            if docker_disponible:
                restore_cmd = f"gunzip -c {ruta_archivo} | docker exec -i osda-supabase-db psql -U postgres -d postgres"
                proc = await _asyncio.create_subprocess_shell(
                    restore_cmd,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                    cwd="/home/openclaw/office-secretary-document-agent"
                )
            else:
                restore_cmd = f"gunzip -c {ruta_archivo} | PGPASSWORD=\"$SUPABASE_DB_PASSWORD\" psql -h supabase-db -U postgres -d postgres"
                proc = await _asyncio.create_subprocess_shell(
                    restore_cmd,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                )
        try:
            salida, _ = await _asyncio.wait_for(proc.communicate(), timeout=300)
        except _asyncio.TimeoutError:
            proc.kill()
            # Intentar reiniciar servicios aunque falle
            for s in servicios:
                await _asyncio.create_subprocess_exec("docker", "compose", "start", s, cwd="/home/openclaw/office-secretary-document-agent")
            raise HTTPException(status_code=500, detail="La restauración excedió 5 minutos; revisar logs")

        if proc.returncode != 0:
            logger.error("backup_restaurar_failed", rc=proc.returncode, salida=salida.decode()[-1000:])
            # Intentar reiniciar servicios solo si docker disponible
            if docker_disponible:
                for s in servicios:
                    await _asyncio.create_subprocess_exec("docker", "compose", "start", s, cwd="/home/openclaw/office-secretary-document-agent")
            raise HTTPException(status_code=500, detail=f"La restauración falló (código {proc.returncode}); ver salida")

        # 3. Reiniciar servicios (solo si docker disponible)
        if docker_disponible:
            for s in servicios:
                proc = await _asyncio.create_subprocess_exec(
                    "docker", "compose", "start", s,
                    stdout=_asyncio.subprocess.DEVNULL,
                    stderr=_asyncio.subprocess.DEVNULL,
                    cwd="/home/openclaw/office-secretary-document-agent"
                )
                await proc.wait()

        # 4. Esperar un poco y verificar
        await _asyncio.sleep(5)

        return {
            "ok": True,
            "archivo": archivo,
            "mensaje": "Base de datos restaurada y servicios reiniciados" if docker_disponible else "Base de datos restaurada",
            "salida": salida.decode()[-2000:],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("backup_restaurar_failed", error=str(e))
        # Intentar reiniciar servicios en caso de error (solo si docker disponible)
        if docker_disponible:
            for s in servicios:
                await _asyncio.create_subprocess_exec("docker", "compose", "start", s, cwd="/home/openclaw/office-secretary-document-agent")
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


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS - CONFIGURACIÓN GENERAL
# ─────────────────────────────────────────────────────────────────

class ConfiguracionGeneral(BaseModel):
    sitio_nombre: str
    sitio_url: str
    zona_horaria: str
    idioma: str
    tamano_maximo_subida: int
    tipos_permitidos: str
    retencion_dias: int
    bucket_storage: str


@app.get("/api/configuracion")
async def get_configuracion(request: Request):
    """Obtener configuración general del sistema (solo ADMIN)."""
    rol = _caller_role(request)
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede ver la configuración")

    try:
        conn = psycopg.connect(
            host="supabase-db",
            dbname="postgres",
            user="postgres",
            password=SUPABASE_DB_PASSWORD,
            port=5432,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM configuracion WHERE id = 1")
            fila = cur.fetchone()
        conn.close()

        if not fila:
            # Retornar valores por defecto si no existe
            return {
                "id": 1,
                "sitio_nombre": "Secretaría",
                "sitio_url": "https://docs.corposcentro.local",
                "zona_horaria": "America/Caracas",
                "idioma": "es",
                "tamano_maximo_subida": 10,
                "tipos_permitidos": "image/jpeg,image/png,application/pdf",
                "retencion_dias": 0,
                "bucket_storage": "documents",
            }

        return {
            "id": fila[0],
            "sitio_nombre": fila[1],
            "sitio_url": fila[2],
            "zona_horaria": fila[3],
            "idioma": fila[4],
            "tamano_maximo_subida": fila[5],
            "tipos_permitidos": fila[6],
            "retencion_dias": fila[7],
            "bucket_storage": fila[8],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_configuracion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/configuracion")
async def update_configuracion(datos: ConfiguracionGeneral, request: Request):
    """Actualizar configuración general (solo ADMIN)."""
    rol = _caller_role(request)
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede actualizar la configuración")

    try:
        conn = psycopg.connect(
            host="supabase-db",
            dbname="postgres",
            user="postgres",
            password=SUPABASE_DB_PASSWORD,
            port=5432,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            # Upsert: insertar si no existe, actualizar si existe
            cur.execute("""
                INSERT INTO configuracion (id, sitio_nombre, sitio_url, zona_horaria, idioma, 
                    tamano_maximo_subida, tipos_permitidos, retencion_dias, bucket_storage)
                VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    sitio_nombre = EXCLUDED.sitio_nombre,
                    sitio_url = EXCLUDED.sitio_url,
                    zona_horaria = EXCLUDED.zona_horaria,
                    idioma = EXCLUDED.idioma,
                    tamano_maximo_subida = EXCLUDED.tamano_maximo_subida,
                    tipos_permitidos = EXCLUDED.tipos_permitidos,
                    retencion_dias = EXCLUDED.retencion_dias,
                    bucket_storage = EXCLUDED.bucket_storage,
                    actualizado_en = NOW()
                RETURNING id
            """, (
                datos.sitio_nombre, datos.sitio_url, datos.zona_horaria, datos.idioma,
                datos.tamano_maximo_subida, datos.tipos_permitidos, 
                datos.retencion_dias, datos.bucket_storage
            ))
            conn.commit()
            fila = cur.fetchone()
        conn.close()

        return {"message": "Configuración actualizada correctamente", "id": fila[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_configuracion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)