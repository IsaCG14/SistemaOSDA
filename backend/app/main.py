"""
FastAPI main application for Office Secretary Document Agent.
"""
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime, date
import os
import re
import logging
import httpx
import psycopg
import uuid
import base64
import structlog
import asyncio
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from jose import jwt as jose_jwt, JWTError
import hmac

# Configuración de logging
logger = structlog.get_logger()

# Configure standard logging
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.DEBUG)

# Variables de entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase-kong:8000")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
OSDA_BOT_SERVICE_KEY = os.getenv("OSDA_BOT_SERVICE_KEY", "")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/backups")
BACKUP_SCRIPT = os.getenv("BACKUP_SCRIPT", "/scripts/backup.sh")
RESTORE_SCRIPT = os.getenv("RESTORE_SCRIPT", "/scripts/restore.sh")

# Clientes HTTP globales
supabase_http_client: Optional[httpx.AsyncClient] = None
graphify_client: Optional[httpx.AsyncClient] = None


# Modelos Pydantic
class DocumentoCreate(BaseModel):
    correlativo: str
    tipo_doc_codigo: str
    oficina_origen_sigla: str
    oficina_destino_sigla: str
    fecha_documento: str
    fecha_recepcion: Optional[str] = None
    remitente: Optional[str] = None
    destinatario: Optional[str] = None
    asunto: Optional[str] = None
    folios: Optional[int] = None
    anexos: Optional[list] = None
    observaciones: Optional[str] = None
    estado: str = "RECIBIDO"
    prioridad: str = "NORMAL"
    confianza_ocr: Optional[float] = None
    telegram_user_id: Optional[int] = None


class DocumentoResponse(BaseModel):
    id: str
    correlativo: str
    tipo_doc_codigo: str
    oficina_origen_sigla: str
    oficina_destino_sigla: str
    fecha_documento: str
    fecha_recepcion: Optional[str] = None
    remitente: Optional[str] = None
    destinatario: Optional[str] = None
    asunto: Optional[str] = None
    folios: Optional[int] = None
    anexos: list = []
    estado: str
    prioridad: str
    observaciones: Optional[str] = None
    confianza_ocr: Optional[float] = None
    telegram_user_id: Optional[int] = None
    creado_en: str
    actualizado_en: str
    creado_por: Optional[str] = None

    class Config:
        from_attributes = True
        # Ignorar campos extra que no están en el modelo
        extra = "ignore"


class ConfiguracionGeneral(BaseModel):
    sitio_nombre: str
    sitio_url: str
    zona_horaria: str
    idioma: str
    tamano_maximo_subida: int
    tipos_permitidos: str
    retencion_dias: int
    bucket_storage: str


class UsuarioCreate(BaseModel):
    nombre: str
    email: str
    password: str
    cargo: Optional[str] = None
    oficina_sigla: str
    telegram_user_id: Optional[int] = None
    username: Optional[str] = None
    role: str = "SECRETARIO"
    activa: bool = True


class UsuarioUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    nombre: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    oficina_sigla: Optional[str] = None
    telegram_user_id: Optional[int] = None
    username: Optional[str] = None
    activa: Optional[bool] = None


class AuthenticatedUser(BaseModel):
    id: Optional[str] = None
    email: Optional[str] = None
    role: str
    oficina_sigla: Optional[str] = None
    is_service: bool = False


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase_http_client, graphify_client

    logger.info("starting_application", environment=ENVIRONMENT)

    # Validar variables críticas al startup
    if not SUPABASE_DB_PASSWORD:
        logger.error("SUPABASE_DB_PASSWORD no configurada - fallará autenticación")

    # Inicializar cliente HTTP para Supabase (PostgREST via Kong)
    supabase_http_client = httpx.AsyncClient(
        base_url=SUPABASE_URL,
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )

    # Inicializar cliente Graphify
    graphify_client = httpx.AsyncClient(
        base_url="http://graphify:8080",
        timeout=30.0,
    )

    yield

    # Cleanup
    await supabase_http_client.aclose()
    await graphify_client.aclose()
    logger.info("application_shutdown")


app = FastAPI(
    title="Office Secretary Document Agent",
    description="API para gestión documental OSDA",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "Content-Range"],
)


# Dependencias
async def get_supabase_client() -> httpx.AsyncClient:
    if supabase_http_client is None:
        raise HTTPException(status_code=503, detail="Cliente Supabase no disponible")
    return supabase_http_client


async def get_graphify_client() -> httpx.AsyncClient:
    if graphify_client is None:
        raise HTTPException(status_code=503, detail="Graphify no disponible")
    return graphify_client


async def get_user_office(request: Request) -> Optional[str]:
    """Obtiene la oficina del usuario autenticado (None para ADMIN)."""
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None

    token = auth.split(" ", 1)[1].strip()
    try:
        from app.core.config import settings
        if not settings.SUPABASE_JWT_SECRET:
            return None
        payload = jose_jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_exp": True},
        )
        email = payload.get("email")
        if not email or supabase_http_client is None:
            return None

        result = await supabase_http_client.get(
            "/rest/v1/personas",
            params={"email": f"eq.{email}", "select": "oficina_sigla", "limit": 1},
        )
        if result.status_code == 200 and result.json():
            return result.json()[0].get("oficina_sigla")
    except Exception:
        pass
    return None


async def get_user_office_and_role(request: Request) -> tuple:
    """Obtiene (oficina_sigla, role) del usuario autenticado."""
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Autenticación requerida")

    token = auth.split(" ", 1)[1].strip()
    try:
        from app.core.config import settings
        if not settings.SUPABASE_JWT_SECRET:
            raise HTTPException(status_code=503, detail="Validación JWT no configurada")
        payload = jose_jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_exp": True},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    email = payload.get("email")
    if not email or supabase_http_client is None:
        raise HTTPException(status_code=401, detail="Usuario no válido")

    result = await supabase_http_client.get(
        "/rest/v1/personas",
        params={"email": f"eq.{email}", "select": "id,email,activa,oficina_sigla", "limit": 1},
    )
    if result.status_code != 200 or not result.json():
        raise HTTPException(status_code=403, detail="Usuario sin permisos en OSDA")

    persona = result.json()[0]
    if not persona.get("activa", False):
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    # El rol se obtiene de user_metadata del JWT verificado
    role = payload.get("user_metadata", {}).get("role")
    if not role:
        role = payload.get("role")
    if not role:
        # Fallback: consultar BD si no viene en token (tokens viejos)
        try:
            with psycopg.connect(
                host="supabase-db", dbname="postgres", user="postgres",
                password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT raw_user_meta_data->>'role' FROM auth.users WHERE lower(email) = lower(%s)",
                        (email,),
                    )
                    row = cursor.fetchone()
                    role = row[0] if row else None
        except psycopg.Error as error:
            logger.error("auth_role_lookup_failed", error=str(error))
            raise HTTPException(status_code=503, detail="No se pudo validar el rol")

    if role not in ("ADMIN", "SECRETARIO"):
        raise HTTPException(status_code=403, detail="Rol no autorizado")

    return (persona.get("oficina_sigla"), role)


async def get_current_user(request: Request) -> AuthenticatedUser:
    """Autenticar JWT de GoTrue o la clave exclusiva del bot."""
    # Verificar clave de servicio del bot
    service_key = os.getenv("OSDA_BOT_SERVICE_KEY", "")
    supplied_key = request.headers.get("x-osda-service-key", "")
    if service_key and supplied_key:
        if hmac.compare_digest(service_key, supplied_key):
            return AuthenticatedUser(role="BOT", is_service=True)
        raise HTTPException(status_code=401, detail="Credencial de servicio inválida")

    # La anon key identifica a Supabase, no autoriza operaciones de OSDA
    if request.headers.get("apikey") == os.getenv("SUPABASE_ANON_KEY", ""):
        raise HTTPException(status_code=401, detail="La anon key no autoriza esta API")

    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Autenticación requerida")

    token = auth.split(" ", 1)[1].strip()
    try:
        from app.core.config import settings
        if not settings.SUPABASE_JWT_SECRET:
            raise HTTPException(status_code=503, detail="Validación JWT no configurada")
        payload = jose_jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_exp": True},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    email = payload.get("email")
    if not email or supabase_http_client is None:
        raise HTTPException(status_code=401, detail="Usuario no válido")

    result = await supabase_http_client.get(
        "/rest/v1/personas",
        params={"email": f"eq.{email}", "select": "id,email,activa,oficina_sigla", "limit": 1},
    )
    if result.status_code != 200 or not result.json():
        raise HTTPException(status_code=403, detail="Usuario sin permisos en OSDA")

    persona = result.json()[0]
    if not persona.get("activa", False):
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    # El rol se obtiene de user_metadata del JWT verificado
    role = payload.get("user_metadata", {}).get("role")
    if not role:
        role = payload.get("role")
    if not role:
        # Fallback: consultar BD si no viene en token (tokens viejos)
        try:
            with psycopg.connect(
                host="supabase-db", dbname="postgres", user="postgres",
                password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT raw_user_meta_data->>'role' FROM auth.users WHERE lower(email) = lower(%s)",
                        (email,),
                    )
                    row = cursor.fetchone()
                    role = row[0] if row else None
        except psycopg.Error as error:
            logger.error("auth_role_lookup_failed", error=str(error))
            raise HTTPException(status_code=503, detail="No se pudo validar el rol")

    if role not in ("ADMIN", "SECRETARIO"):
        raise HTTPException(status_code=403, detail="Rol no autorizado")

    return AuthenticatedUser(
        id=persona.get("id"),
        email=persona.get("email"),
        role=role,
        oficina_sigla=persona.get("oficina_sigla"),
    )


async def _verify_admin_role(request: Request) -> str:
    """Verifica que el usuario sea ADMIN usando el rol del JWT."""
    from app.core.config import settings

    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")

    token = auth.split(" ", 1)[1].strip()
    try:
        if not settings.SUPABASE_JWT_SECRET:
            raise HTTPException(status_code=503, detail="Validación JWT no configurada")
        payload = jose_jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_exp": True},
        )
        # GoTrue pone el rol de la aplicación en user_metadata.role
        user_role = payload.get("user_metadata", {}).get("role")
        if not user_role:
            # Fallback: claim "role" estándar (puede ser "authenticated" en GoTrue)
            user_role = payload.get("role")

        if user_role != "ADMIN":
            raise HTTPException(status_code=403, detail="Solo un ADMIN puede acceder a personas")

        return user_role

    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    except Exception as e:
        logger.error("_verify_admin_role_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Error verificando token")


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - HEALTH CHECK
# ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    from app.core.config import settings

    # Verificar Supabase
    supabase_status = "disconnected"
    try:
        if supabase_http_client:
            r = await supabase_http_client.get("/rest/v1/", timeout=5)
            if r.status_code == 200:
                supabase_status = "connected"
    except Exception:
        pass

    # Verificar NVIDIA API (Vision) - solo si es el proveedor configurado
    nvidia_status = "not_configured"
    if settings.VISION_PROVIDER == "nvidia" and settings.NVIDIA_API_KEY:
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(
                    "https://integrate.api.nvidia.com/v1/models",
                    headers={"Authorization": f"Bearer {settings.NVIDIA_API_KEY}"},
                    timeout=5,
                )
                if r.status_code == 200:
                    nvidia_status = "connected"
        except Exception:
            pass
    elif settings.VISION_PROVIDER == "ollama":
        nvidia_status = "using_ollama"

    # Verificar Ollama
    ollama_status = "disconnected"
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
            if r.status_code == 200:
                ollama_status = "connected"
    except Exception:
        pass

    # Verificar Graphify
    graphify_status = "disconnected"
    try:
        if graphify_client:
            r = await graphify_client.get("/health", timeout=5)
            if r.status_code == 200:
                graphify_status = "connected"
    except Exception:
        pass

    # Verificar BD
    db_status = "disconnected"
    try:
        with psycopg.connect(
            host="supabase-db", dbname="postgres", user="postgres",
            password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_status = "connected"
    except Exception:
        pass

    overall = "healthy" if all(
        s in ("connected", "using_ollama") for s in [supabase_status, db_status, ollama_status, graphify_status]
    ) else "degraded"

    return {
        "status": overall,
        "services": {
            "supabase": supabase_status,
            "database": db_status,
            "ollama": ollama_status,
            "nvidia_vision": nvidia_status,
            "graphify": graphify_status,
        },
        "version": "1.0.0",
        "environment": ENVIRONMENT,
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - MÉTRICAS DASHBOARD
# ─────────────────────────────────────────────────────────────────
@app.get("/api/documentos/metricas")
async def get_metricas(
    request: Request,
    oficina_origen: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    user_office: Optional[str] = Depends(get_user_office),
    client: httpx.AsyncClient = Depends(get_supabase_client),
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
            params.append(("fecha_documento", f"gte.{fecha_desde}"))
            params.append(("fecha_documento", f"lte.{fecha_hasta}"))
        elif fecha_desde:
            params.append(("fecha_documento", f"gte.{fecha_desde}"))
        elif fecha_hasta:
            params.append(("fecha_documento", f"lte.{fecha_hasta}"))

        # EXCLUIR documentos eliminados (soft delete)
        params.append(("eliminado_en", "is.null"))

        # Construir filtro de oficina base para reutilizar
        oficina_filter = None
        if user_office:
            oficina_filter = ("or", f"(oficina_origen_sigla.eq.{user_office},oficina_destino_sigla.eq.{user_office})")
        elif oficina_origen:
            oficina_filter = ("oficina_origen_sigla", f"eq.{oficina_origen}")

        if oficina_filter:
            params.append(oficina_filter)

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
        hoy = date.today()
        inicio_mes = date(hoy.year, hoy.month, 1).isoformat()

        params_mes = [("select", "id")]

        if oficina_filter:
            params_mes.append(oficina_filter)

        if tipo_documento:
            params_mes.append(("tipo_doc_codigo", f"eq.{tipo_documento}"))

        params_mes.append(("fecha_documento", f"gte.{inicio_mes}"))
        params_mes.append(("eliminado_en", "is.null"))

        result_mes = await client.get("/rest/v1/documentos", params=params_mes)
        result_mes.raise_for_status()
        docs_mes = result_mes.json()
        este_mes = len(docs_mes)

        # Oficinas activas
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


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - DOCUMENTOS
# ─────────────────────────────────────────────────────────────────
@app.post("/api/documentos", response_model=DocumentoResponse, status_code=201)
async def create_documento(
    data: DocumentoCreate,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Crear nuevo documento."""
    if user.role == "SECRETARIO" and user.oficina_sigla:
        if data.oficina_origen_sigla != user.oficina_sigla and data.oficina_destino_sigla != user.oficina_sigla:
            raise HTTPException(status_code=403, detail="Solo puedes crear documentos de tu oficina")

    try:
        payload = data.model_dump()
        payload["creado_por"] = user.id
        payload["actualizado_por"] = user.id

        result = await client.post("/rest/v1/documentos", json=payload, headers={"Prefer": "return=representation"})
        result.raise_for_status()
        created = result.json()

        # Indexar en Graphify
        try:
            if graphify_client:
                doc_id = created[0]["id"]
                graphify_payload = {
                    "id": doc_id,
                    "correlativo": data.correlativo,
                    "tipo_documento": data.tipo_doc_codigo,
                    "oficina_origen": data.oficina_origen_sigla,
                    "oficina_destino": data.oficina_destino_sigla,
                    "fecha_documento": data.fecha_documento,
                    "fecha_recepcion": data.fecha_recepcion,
                    "remitente": data.remitente,
                    "destinatario": data.destinatario,
                    "asunto": data.asunto,
                    "folios": data.folios,
                    "anexos": data.anexos or [],
                    "estado": data.estado,
                    "prioridad": data.prioridad,
                    "observaciones": data.observaciones,
                    "confianza_ocr": data.confianza_ocr,
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


@app.get("/api/documentos", response_model=list[DocumentoResponse])
async def list_documentos(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    estado: Optional[str] = None,
    tipo_doc_codigo: Optional[str] = None,
    oficina_origen_sigla: Optional[str] = None,
    oficina_destino_sigla: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    order_by: str = "fecha_documento",
    order_dir: str = "desc",
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Listar documentos con filtros y paginación."""
    user_office, user_role = user_info

    params = {
        "limit": limit,
        "offset": offset,
        "order": f"{order_by}.{order_dir}",
    }

    # Filtrado por oficina
    if user_role == "SECRETARIO" and user_office:
        params["or"] = f"(oficina_origen_sigla.eq.{user_office},oficina_destino_sigla.eq.{user_office})"
    else:
        # ADMIN: filtros manuales
        if oficina_origen_sigla:
            params["oficina_origen_sigla"] = f"eq.{oficina_origen_sigla}"
        if oficina_destino_sigla:
            params["oficina_destino_sigla"] = f"eq.{oficina_destino_sigla}"

    if search:
        params["or"] = f"(correlativo.ilike.*{search}*,asunto.ilike.*{search}*,remitente.ilike.*{search}*,destinatario.ilike.*{search}*)"
    if estado:
        params["estado"] = f"eq.{estado}"
    if tipo_doc_codigo:
        params["tipo_doc_codigo"] = f"eq.{tipo_doc_codigo}"
    if fecha_desde:
        params["fecha_documento"] = f"gte.{fecha_desde}"
    if fecha_hasta:
        # PostgREST no soporta múltiples valores para mismo key, usar dos queries o lte
        params["fecha_documento"] = f"lte.{fecha_hasta}"

    # Excluir eliminados
    params["eliminado_en"] = "is.null"

    try:
        result = await client.get("/rest/v1/documentos", params=params)
        result.raise_for_status()
        return [DocumentoResponse(**doc) for doc in result.json()]
    except httpx.HTTPStatusError as e:
        logger.error("list_documentos_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error listando documentos: {e.response.text}")
    except Exception as e:
        logger.error("list_documentos_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documentos/{doc_id}", response_model=DocumentoResponse)
async def get_documento(
    doc_id: str,
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_supabase_client),
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
            if doc.get("oficina_origen_sigla") != user_office and doc.get("oficina_destino_sigla") != user_office:
                raise HTTPException(status_code=403, detail="Sin acceso a este documento")

        return DocumentoResponse(**doc)
    except httpx.HTTPStatusError as e:
        logger.error("get_documento_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error obteniendo documento: {e.response.text}")
    except Exception as e:
        logger.error("get_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/documentos/{doc_id}", response_model=DocumentoResponse)
async def update_documento(
    doc_id: str,
    data: DocumentoCreate,
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Actualizar documento."""
    user_office, user_role = user_info

    try:
        # Verificar existencia y acceso
        result = await client.get(f"/rest/v1/documentos?id=eq.{doc_id}")
        result.raise_for_status()
        existing = result.json()
        if not existing:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        doc = existing[0]
        if user_role != "ADMIN":
            if doc.get("oficina_origen_sigla") != user_office and doc.get("oficina_destino_sigla") != user_office:
                raise HTTPException(status_code=403, detail="Sin acceso a este documento")

        # Actualizar
        payload = data.model_dump()
        payload["actualizado_por"] = user_office  # o user.id si se pasa
        payload["actualizado_en"] = datetime.utcnow().isoformat()

        result = await client.patch(f"/rest/v1/documentos?id=eq.{doc_id}", json=payload, headers={"Prefer": "return=representation"})
        result.raise_for_status()
        updated = result.json()

        # Re-indexar en Graphify
        try:
            if graphify_client:
                graphify_payload = {
                    "id": doc_id,
                    "correlativo": data.correlativo,
                    "tipo_documento": data.tipo_doc_codigo,
                    "oficina_origen": data.oficina_origen_sigla,
                    "oficina_destino": data.oficina_destino_sigla,
                    "fecha_documento": data.fecha_documento,
                    "fecha_recepcion": data.fecha_recepcion,
                    "remitente": data.remitente,
                    "destinatario": data.destinatario,
                    "asunto": data.asunto,
                    "folios": data.folios,
                    "anexos": data.anexos or [],
                    "estado": data.estado,
                    "prioridad": data.prioridad,
                    "observaciones": data.observaciones,
                    "confianza_ocr": data.confianza_ocr,
                }
                await graphify_client.patch(f"/documentos/{doc_id}", json=graphify_payload, timeout=10)
        except Exception as e:
            logger.warning("graphify_update_failed", error=str(e), doc_id=doc_id)

        return DocumentoResponse(**updated[0])
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
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Eliminar documento (soft delete)."""
    user_office, user_role = user_info

    try:
        result = await client.get(f"/rest/v1/documentos?id=eq.{doc_id}")
        result.raise_for_status()
        existing = result.json()
        if not existing:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        doc = existing[0]
        if user_role != "ADMIN":
            if doc.get("oficina_origen_sigla") != user_office and doc.get("oficina_destino_sigla") != user_office:
                raise HTTPException(status_code=403, detail="Sin acceso a este documento")

        # Soft delete
        payload = {"eliminado_en": datetime.utcnow().isoformat()}
        result = await client.patch(f"/rest/v1/documentos?id=eq.{doc_id}", json=payload, headers={"Prefer": "return=representation"})
        result.raise_for_status()

        # Eliminar de Graphify
        try:
            if graphify_client:
                await graphify_client.delete(f"/documentos/{doc_id}", timeout=10)
        except Exception as e:
            logger.warning("graphify_delete_failed", error=str(e), doc_id=doc_id)

        return {"message": "Documento eliminado", "id": doc_id}
    except httpx.HTTPStatusError as e:
        logger.error("delete_documento_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail=f"Error eliminando documento: {e.response.text}")
    except Exception as e:
        logger.error("delete_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - CONSULTAS (PENDIENTES, HUECOS, ETC)
# ─────────────────────────────────────────────────────────────────
@app.get("/api/consultas/pendientes")
async def get_pendientes(
    request: Request,
    oficina: Optional[str] = None,
    tipo: Optional[str] = None,
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Obtener correlativos pendientes por oficina/tipo."""
    try:
        params = {"select": "correlativo", "eliminado_en": "is.null", "order": "correlativo"}
        if oficina:
            params["oficina_origen_sigla"] = f"eq.{oficina}"
        if tipo:
            params["tipo_doc_codigo"] = f"eq.{tipo}"

        result = await client.get("/rest/v1/documentos", params=params)
        result.raise_for_status()
        docs = result.json()

        # Extraer números y encontrar huecos
        correlativos = [d["correlativo"] for d in docs if d.get("correlativo")]
        # Lógica simplificada - en producción usar la función detectar_huecos
        return {"pendientes": correlativos, "total": len(correlativos)}
    except Exception as e:
        logger.error("get_pendientes_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/consultas/por-oficina")
async def por_oficina(
    oficina: str,
    tipo_documento: Optional[str] = None,
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    limit: int = 50,
    graphify_client: httpx.AsyncClient = Depends(get_graphify_client),
):
    """Consultar documentos por oficina desde Graphify."""
    try:
        params = {"oficina": oficina, "limit": limit}
        if tipo_documento:
            params["tipo_documento"] = tipo_documento
        if mes:
            params["mes"] = mes
        if anio:
            params["anio"] = anio

        result = await graphify_client.get("/consultas/por-oficina", params=params)
        result.raise_for_status()
        return result.json()
    except Exception as e:
        logger.error("por_oficina_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────
@app.get("/api/configuracion")
async def get_configuracion(
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
):
    """Obtener configuración general del sistema (solo ADMIN)."""
    user_office, rol = user_info
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede ver la configuración")

    try:
        with psycopg.connect(
            host="supabase-db", dbname="postgres", user="postgres",
            password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM configuracion WHERE id = 1")
                fila = cur.fetchone()

        if not fila:
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
async def update_configuracion(
    datos: ConfiguracionGeneral,
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
):
    """Actualizar configuración general (solo ADMIN)."""
    user_office, rol = user_info
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede actualizar la configuración")

    try:
        with psycopg.connect(
            host="supabase-db", dbname="postgres", user="postgres",
            password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
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
                """, (
                    datos.sitio_nombre, datos.sitio_url, datos.zona_horaria, datos.idioma,
                    datos.tamano_maximo_subida, datos.tipos_permitidos,
                    datos.retencion_dias, datos.bucket_storage,
                ))
                conn.commit()
        return {"message": "Configuración actualizada correctamente", "id": 1}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_configuracion_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - BACKUP
# ─────────────────────────────────────────────────────────────────
@app.get("/api/backup/listar")
async def listar_backups(
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
):
    """Listar respaldos existentes con tamaño y fecha (solo ADMIN)."""
    user_office, rol = user_info
    if rol != "ADMIN":
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
async def ejecutar_backup(
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
):
    """Ejecutar backup AHORA (solo ADMIN)."""
    user_office, rol = user_info
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede ejecutar respaldos")

    if not os.path.exists(BACKUP_SCRIPT):
        raise HTTPException(status_code=500, detail="Script de backup no encontrado en el backend")

    try:
        antes = set(os.listdir(BACKUP_DIR)) if os.path.isdir(BACKUP_DIR) else set()
        proc = await asyncio.create_subprocess_exec(
            "bash", BACKUP_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            salida, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
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
async def restaurar_backup(
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
):
    """Restaurar base de datos desde un backup (solo ADMIN)."""
    user_office, rol = user_info
    if rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo un ADMIN puede restaurar respaldos")

    import asyncio as _asyncio
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

    servicios = ["backend", "telegram-bot", "graphify", "migrator"]

    import shutil
    docker_disponible = shutil.which("docker") is not None

    try:
        if docker_disponible:
            for s in servicios:
                proc = await _asyncio.create_subprocess_exec(
                    "docker", "compose", "stop", s,
                    stdout=_asyncio.subprocess.DEVNULL,
                    stderr=_asyncio.subprocess.DEVNULL,
                    cwd="/home/openclaw/office-secretary-document-agent"
                )
                await proc.wait()

        if es_dump_custom:
            proc = await _asyncio.create_subprocess_exec(
                "pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges",
                "--dbname=postgresql://postgres:postgres@supabase-db:5432/postgres",
                ruta_archivo,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
            )
            await proc.wait()
        else:
            proc = await _asyncio.create_subprocess_exec(
                "gunzip", "-c", ruta_archivo,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
            )
            gunzip_out, _ = await proc.communicate()
            proc = await _asyncio.create_subprocess_exec(
                "psql", "-h", "supabase-db", "-U", "postgres", "-d", "postgres",
                stdin=_asyncio.subprocess.PIPE,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
            )
            await proc.communicate(input=gunzip_out)

        if docker_disponible:
            for s in servicios:
                proc = await _asyncio.create_subprocess_exec(
                    "docker", "compose", "start", s,
                    stdout=_asyncio.subprocess.DEVNULL,
                    stderr=_asyncio.subprocess.DEVNULL,
                    cwd="/home/openclaw/office-secretary-document-agent"
                )
                await proc.wait()

        return {"ok": True, "mensaje": f"Restaurado desde {archivo}"}
    except Exception as e:
        logger.error("backup_restaurar_failed", error=str(e))
        if docker_disponible:
            for s in servicios:
                try:
                    proc = await _asyncio.create_subprocess_exec(
                        "docker", "compose", "start", s,
                        stdout=_asyncio.subprocess.DEVNULL,
                        stderr=_asyncio.subprocess.DEVNULL,
                        cwd="/home/openclaw/office-secretary-document-agent"
                    )
                    await proc.wait()
                except Exception:
                    pass
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - PERSONAS / USUARIOS
# ─────────────────────────────────────────────────────────────────
@app.get("/api/oficinas")
async def listar_oficinas(
    request: Request,
    active_only: bool = True,
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Listar oficinas (público para selects)."""
    params = {
        "order": "sigla.asc",
    }
    if active_only:
        params["activa"] = "eq.true"

    try:
        result = await client.get("/rest/v1/oficinas", params=params)
        result.raise_for_status()
        return result.json()
    except Exception as e:
        logger.error("listar_oficinas_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tipos-documento")
async def listar_tipos_documento(
    request: Request,
    active_only: bool = True,
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Listar tipos de documento (público para selects)."""
    params = {
        "order": "codigo.asc",
    }
    if active_only:
        params["activo"] = "eq.true"

    try:
        result = await client.get("/rest/v1/tipos_documento", params=params)
        result.raise_for_status()
        return result.json()
    except Exception as e:
        logger.error("listar_tipos_documento_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/personas")
async def listar_personas(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = True,
    rol: str = Depends(_verify_admin_role),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Listar personas (solo ADMIN)."""
    params = {
        "limit": limit,
        "offset": offset,
        "order": "nombre.asc",
    }
    if active_only:
        params["activa"] = "eq.true"

    try:
        result = await client.get("/rest/v1/personas", params=params)
        result.raise_for_status()
        personas = result.json()

        # Enriquecer con el rol real, que vive en auth.users (user_metadata),
        # no en la tabla personas. Mapea por id (personas.id == auth.users.id).
        if personas:
            roles = {}
            try:
                with psycopg.connect(
                    host="supabase-db", dbname="postgres", user="postgres",
                    password=SUPABASE_DB_PASSWORD, port=5432, connect_timeout=5,
                ) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT id, raw_user_meta_data->>'role' FROM auth.users WHERE id = ANY(%s)",
                            ([p["id"] for p in personas],),
                        )
                        for uid, role in cursor.fetchall():
                            roles[str(uid)] = role
            except psycopg.Error as error:
                logger.error("listar_personas_roles_failed", error=str(error))

            for p in personas:
                p["role"] = roles.get(str(p.get("id"))) or "SECRETARIO"

        return personas
    except HTTPException:
        raise
    except Exception as e:
        logger.error("listar_personas_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/personas", status_code=201)
async def crear_persona(
    request: Request,
    rol: str = Depends(_verify_admin_role),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Crear persona (solo ADMIN)."""
    body = await request.json()
    try:
        result = await client.post("/rest/v1/personas", json=body, headers={"Prefer": "return=representation"})
        result.raise_for_status()
        return result.json()[0]
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"Error creando persona: {e.response.text}")


@app.patch("/api/personas/{persona_id}")
async def actualizar_persona(
    persona_id: str,
    request: Request,
    rol: str = Depends(_verify_admin_role),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Actualizar persona (solo ADMIN)."""
    body = await request.json()
    try:
        result = await client.patch(f"/rest/v1/personas?id=eq.{persona_id}", json=body, headers={"Prefer": "return=representation"})
        result.raise_for_status()
        if not result.json():
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        return result.json()[0]
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando persona: {e.response.text}")


@app.delete("/api/personas/{persona_id}")
async def eliminar_persona(
    persona_id: str,
    request: Request,
    rol: str = Depends(_verify_admin_role),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Eliminar persona (solo ADMIN)."""
    try:
        result = await client.delete(f"/rest/v1/personas?id=eq.{persona_id}", headers={"Prefer": "return=representation"})
        if result.status_code == 200:
            return {"message": "Persona eliminada", "id": persona_id}
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando persona: {e.response.text}")




@app.get("/api/personas/username/{username}/email")
async def get_email_by_username(
    username: str,
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Endpoint publico para obtener email dado un username (para login)."""
    try:
        result = await client.get(
            "/rest/v1/personas",
            params={
                "username": f"eq.{username}",
                "select": "email",
                "limit": 1,
            }
        )
        result.raise_for_status()
        data = result.json()
        if not data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"email": data[0]["email"]}
    except httpx.HTTPStatusError as e:
        logger.error("get_email_by_username_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail="Error consultando usuario")
    except Exception as e:
        logger.error("get_email_by_username_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/personas/me/oficina")
async def get_persona_oficina(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Obtener oficina del usuario autenticado."""
    try:
        result = await client.get(
            "/rest/v1/personas",
            params={
                "id": f"eq.{current_user.id}",
                "select": "oficina_sigla,nombre",
                "limit": 1,
            }
        )
        result.raise_for_status()
        data = result.json()
        if not data:
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        return {"oficina_sigla": data[0].get("oficina_sigla"), "nombre": data[0].get("nombre")}
    except httpx.HTTPStatusError as e:
        logger.error("get_persona_oficina_failed", error=str(e), response=e.response.text)
        raise HTTPException(status_code=500, detail="Error consultando oficina")
    except Exception as e:
        logger.error("get_persona_oficina_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - USUARIOS UNIFICADO
# ─────────────────────────────────────────────────────────────────
@app.post("/api/usuarios", status_code=201)
async def crear_usuario(
    data: UsuarioCreate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Crear usuario completo: Auth + Persona en una sola llamada."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo ADMIN puede crear usuarios")

    try:
        # 1. Crear en Auth (GoTrue via Kong admin API)
        async with httpx.AsyncClient(
            base_url=SUPABASE_URL,
            headers={"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
            timeout=30.0,
        ) as admin_client:
            auth_payload = {
                "email": data.email,
                "password": data.password,
                "email_confirm": True,
                "user_metadata": {
                    "nombre": data.nombre,
                    "role": data.role,
                    "username": data.username or data.email.split("@")[0],
                }
            }
            auth_resp = await admin_client.post("/auth/v1/admin/users", json=auth_payload)
            if auth_resp.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Error en Auth: {auth_resp.text}")
            auth_user = auth_resp.json()
            user_id = auth_user["id"]

        # 2. Crear en personas
        persona_payload = {
            "id": user_id,
            "nombre": data.nombre,
            "cargo": data.cargo,
            "oficina_sigla": data.oficina_sigla,
            "telegram_user_id": data.telegram_user_id,
            "username": data.username,
            "email": data.email,
            "activa": data.activa,
        }
        async with httpx.AsyncClient(
            base_url=SUPABASE_URL,
            headers={"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
            timeout=30.0,
        ) as admin_client:
            persona_resp = await admin_client.post("/rest/v1/personas", json=persona_payload, headers={"Prefer": "return=representation"})
            persona_resp.raise_for_status()

        return {"message": "Usuario creado", "id": user_id}
    except Exception as e:
        logger.error("crear_usuario_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/usuarios/{usuario_id}")
async def actualizar_usuario(
    usuario_id: str,
    data: UsuarioUpdate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Actualizar usuario (Auth y/o Persona)."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo ADMIN puede actualizar usuarios")

    try:
        # Actualizar Auth si se proporciona password/email/role
        if data.password or data.email or data.role:
            async with httpx.AsyncClient(
                base_url=SUPABASE_URL,
                headers={"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
                timeout=30.0,
            ) as admin_client:
                auth_payload = {}
                if data.password:
                    auth_payload["password"] = data.password
                if data.email:
                    auth_payload["email"] = data.email
                if data.role:
                    auth_payload["user_metadata"] = {"role": data.role}
                auth_resp = await admin_client.put(f"/auth/v1/admin/users/{usuario_id}", json=auth_payload)
                if auth_resp.status_code not in (200, 204):
                    logger.warning("auth_update_warning", status=auth_resp.status_code, resp=auth_resp.text)

        # Actualizar persona
        # Nota: "role" NO existe en la tabla personas; el rol vive en user_metadata de Auth.
        persona_payload = {}
        if data.nombre is not None:
            persona_payload["nombre"] = data.nombre
        if data.cargo is not None:
            persona_payload["cargo"] = data.cargo
        if data.oficina_sigla is not None:
            persona_payload["oficina_sigla"] = data.oficina_sigla
        if data.telegram_user_id is not None:
            persona_payload["telegram_user_id"] = data.telegram_user_id
        if data.username is not None:
            persona_payload["username"] = data.username
        if data.email is not None:
            persona_payload["email"] = data.email
        if data.activa is not None:
            persona_payload["activa"] = data.activa

        if persona_payload:
            async with httpx.AsyncClient(
                base_url=SUPABASE_URL,
                headers={"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
                timeout=30.0,
            ) as admin_client:
                persona_resp = await admin_client.patch(
                    f"/rest/v1/personas?id=eq.{usuario_id}",
                    json=persona_payload,
                    headers={"Prefer": "return=representation"}
                )
                persona_resp.raise_for_status()
                if not persona_resp.json():
                    raise HTTPException(status_code=404, detail="Usuario no encontrado en personas")

        return {"message": "Usuario actualizado", "id": usuario_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("actualizar_usuario_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/usuarios/{usuario_id}")
async def eliminar_usuario(
    usuario_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Eliminar usuario completo: Auth + Persona (solo ADMIN)."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo ADMIN puede eliminar usuarios")

    try:
        async with httpx.AsyncClient(
            base_url=SUPABASE_URL,
            headers={"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
            timeout=30.0,
        ) as admin_client:
            await admin_client.delete(f"/auth/v1/admin/users/{usuario_id}")
            await admin_client.delete(f"/rest/v1/personas?id=eq.{usuario_id}")

        return {"message": "Usuario eliminado", "id": usuario_id}
    except Exception as e:
        logger.error("eliminar_usuario_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - GRAPHIFY TRACE
# ─────────────────────────────────────────────────────────────────
@app.get("/api/graphify/trace/{correlativo}")
async def graphify_trace(
    correlativo: str,
    request: Request,
    user_info: tuple = Depends(get_user_office_and_role),
    client: httpx.AsyncClient = Depends(get_graphify_client),
):
    """Obtener trazabilidad de un documento desde Graphify."""
    try:
        result = await client.get(f"/trace/{correlativo}")
        result.raise_for_status()
        return result.json()
    except Exception as e:
        logger.error("graphify_trace_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# ENDPOINT - WEBHOOK TELEGRAM
# ─────────────────────────────────────────────────────────────────
@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    client: httpx.AsyncClient = Depends(get_supabase_client),
):
    """Webhook para Telegram (opcional, si no se usa polling)."""
    # Por ahora solo logging - el bot usa polling
    body = await request.json()
    logger.info("telegram_webhook_received", update_id=body.get("update_id"))
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)