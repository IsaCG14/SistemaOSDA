"""
Cliente async de la API del backend OSDA (SOLO LECTURA).

El bot consulta documentos a Postgres via el backend FastAPI, que ya
soporta: search (sin acentos), tipo_documento, estado, oficinas y
rangos de fecha. El grafo Neo4j queda solo para trazabilidad (/traza).
"""
import calendar
import httpx
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_URL = "http://osda-backend:8000/api/documentos"

TIPOS_VALIDOS = [
    "MEMO", "OFICIO", "CIRCULAR", "INFORME", "NOTA",
    "ACTA", "RESOLUCION", "SOLICITUD", "RECIBO", "OTRO",
]

ESTADOS_VALIDOS = [
    "RECIBIDO", "EN_TRAMITE", "RESPONDIDO", "ARCHIVADO",
    "DERIVADO", "RECHAZADO", "EXTRAVIADO",
]


async def consultar_documentos(
    search: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    estado: Optional[str] = None,
    oficina_origen: Optional[str] = None,
    oficina_destino: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Consultar documentos al backend. Devuelve lista de dicts (puede ser vacia)."""
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    if tipo_documento:
        params["tipo_documento"] = tipo_documento
    if estado:
        params["estado"] = estado
    if oficina_origen:
        params["oficina_origen"] = oficina_origen
    if oficina_destino:
        params["oficina_destino"] = oficina_destino
    if fecha_desde:
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        params["fecha_hasta"] = fecha_hasta
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"consultar_documentos_failed: {e}")
        raise


def parsear_fecha(texto: str) -> Optional[Tuple[str, str]]:
    """Parsear fechas en formato venezolano/ISO a un rango (desde, hasta).

    Acepta:
      DD/MM/AAAA o DD-MM-AAAA  -> ese dia exacto
      MM/AAAA  o MM-AAAA       -> todo el mes
      AAAA                       -> todo el anio

    Devuelve ("YYYY-MM-DD", "YYYY-MM-DD") o None si es invalido.
    """
    t = texto.strip()
    if not t:
        return None

    # DD/MM/AAAA o DD-MM-AAAA
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", t)
    if m:
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mes <= 12 and 1 <= d <= 31):
            return None
        try:
            ultimo = calendar.monthrange(a, mes)[1]
        except Exception:
            return None
        if d > ultimo:
            return None
        return (f"{a:04d}-{mes:02d}-{d:02d}", f"{a:04d}-{mes:02d}-{d:02d}")

    # MM/AAAA o MM-AAAA
    m = re.match(r"^(\d{1,2})[-/](\d{4})$", t)
    if m:
        mes, a = int(m.group(1)), int(m.group(2))
        if not (1 <= mes <= 12):
            return None
        ultimo = calendar.monthrange(a, mes)[1]
        return (f"{a:04d}-{mes:02d}-01", f"{a:04d}-{mes:02d}-{ultimo:02d}")

    # AAAA
    m = re.match(r"^(\d{4})$", t)
    if m:
        a = int(m.group(1))
        return (f"{a}-01-01", f"{a}-12-31")

    return None


def extraer_tipo(args: List[str]) -> Tuple[Optional[str], List[str]]:
    """Si el ultimo argumento es un tipo valido, separarlo del resto.

    /fecha 08/2026 memos -> ("MEMO", ["08/2026"])
    Devuelve (None, args_intactos) si no hay tipo.
    """
    if args and args[-1].upper() in TIPOS_VALIDOS:
        return args[-1].upper(), args[:-1]
    return None, args
