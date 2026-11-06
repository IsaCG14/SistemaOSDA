"""
Telegram Bot Handlers for document processing workflow.
"""
import logging
import httpx
import re
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.core.config import settings, get_settings_instance

logger = logging.getLogger(__name__)

# Estados de conversación para corrección
CORRECTION_FIELD = "correction_field"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Bienvenida."""
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return  # Silencioso: no responde en topics no autorizados
    
    welcome = (
        "🤖 **Office Secretary Document Agent**\n\n"
        "Envía una foto o PDF de un documento y extraeré los datos automáticamente.\n\n"
        "**Consultas:**\n"
        "/doc <correlativo> — ficha de un documento\n"
        "/documentos [tipo] — listado paginado\n"
        "/memos /notas /oficios /informes — atajos por tipo\n"
        "/buscar <término> — búsqueda (ignora acentos)\n"
        "/fecha <DD/MM/AAAA | MM/AAAA | AAAA> [tipo]\n"
        "/estado <estado> — por estado del trámite\n"
        "/oficina <sigla> [origen|destino]\n"
        "/resumen — métricas rápidas\n\n"
        "**Registro:**\n"
        "/pendientes — documentos pendientes\n"
        "/correlativo <oficina> <tipo> — último correlativo\n\n"
        "**Catálogos:**\n"
        "/oficinas · /tipos · /ayuda"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def ayuda_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ayuda."""
    await start_command(update, context)


async def oficinas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /oficinas - Listar oficinas."""
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return
    
    try:
        # Aquí se consultaría Graphify o Supabase
        # Por ahora respuesta estática
        texto = "🏢 **Oficinas registradas:**\n\n"
        oficinas = [
            ("OTIC", "Oficina de Tecnología de Información y Comunicación"),
            ("OGA", "Oficina de Gestión Administrativa"),
            ("OGH", "Oficina de Gestión Humana"),
            ("OPP", "Oficina de Planificación y Presupuesto"),
            ("DP", "Dirección de Planificación"),
            ("DG", "Dirección General"),
            ("UAI", "Unidad de Auditoría Interna"),
            ("OAC", "Oficina de Administración y Contabilidad"),
        ]
        for sigla, nombre in oficinas:
            texto += f"• `{sigla}` - {nombre}\n"
        
        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en oficinas_command: {e}")
        await update.message.reply_text("❌ Error obteniendo oficinas")


async def tipos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /tipos - Listar tipos de documento."""
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return
    
    texto = "📋 **Tipos de documento:**\n\n"
    tipos = [
        ("MEMO", "Memorándum", "5 días"),
        ("OFICIO", "Oficio", "10 días"),
        ("CIRCULAR", "Circular", "3 días"),
        ("INFORME", "Informe", "15 días"),
        ("NOTA", "Nota / Nota de Entrega", "2 días"),
        ("ACTA", "Acta", "N/A"),
        ("RESOLUCION", "Resolución", "N/A"),
        ("SOLICITUD", "Solicitud", "10 días"),
        ("RECIBO", "Recibo", "N/A"),
        ("OTRO", "Otro tipo de documento", "5 días"),
    ]
    
    for codigo, nombre, plazo in tipos:
        texto += f"• `{codigo}` - {nombre} (plazo: {plazo})\n"
    
    await update.message.reply_text(texto, parse_mode="Markdown")


async def pendientes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pendientes - Ver documentos pendientes."""
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return
    
    # Import here to ensure PYTHONPATH is set
    from app.services.graphify_client import graphify_client
    
    try:
        docs = await graphify_client.get_pending_documents()
        
        if docs:
            texto = f"⏳ **Documentos pendientes ({len(docs)}):**\n\n"
            for d in docs[:10]:
                texto += f"• `{d.get('correlativo', 'N/A')}` - {d.get('asunto', 'Sin asunto')[:50]}\n"
                texto += f"  📅 Recibido: {d.get('fecha_recepcion', 'N/A')} | 🏢 {d.get('oficina_origen_sigla', 'N/A')} → {d.get('oficina_destino_sigla', 'N/A')}\n"
            if len(docs) > 10:
                texto += f"\n... y {len(docs) - 10} más"
        else:
            texto = "✅ No hay documentos pendientes."
        
        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en pendientes_command: {e}")
        await update.message.reply_text("❌ Error consultando pendientes")


async def correlativo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /correlativo <oficina> <tipo> - Último correlativo."""
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: `/correlativo <oficina> <tipo>`\n"
            "Ej: `/correlativo OTIC MEMO`",
            parse_mode="Markdown"
        )
        return
    
    oficina, tipo = args[0].upper(), args[1].upper()
    
    # Import here to ensure PYTHONPATH is set
    from app.services.graphify_client import graphify_client
    
    try:
        result = await graphify_client.get_last_correlativo(oficina, tipo)
        
        if result and result.get("correlativo"):
            await update.message.reply_text(
                f"🔢 **Último correlativo:**\n"
                f"`{result['correlativo']}`\n"
                f"📅 Fecha: {result.get('fecha', 'N/A')}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"📭 No hay correlativos para {oficina} - {tipo}")
    except Exception as e:
        logger.error(f"Error en correlativo_command: {e}")
        await update.message.reply_text("❌ Error consultando correlativo")


async def buscar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /buscar <término> - Buscar documentos."""
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Uso: `/buscar <término>`", parse_mode="Markdown")
        return
    
    termino = " ".join(args)
    
    try:
        # Buscar en el backend (Postgres): search sin acentos, mas completo que el grafo
        from bot.core.backend_client import consultar_documentos
        results = await consultar_documentos(search=termino, limit=10)
        
        if results:
            texto = f"🔍 **Resultados para '{termino}' ({len(results)}):**\n\n"
            for d in results:
                texto += f"• `{d.get('correlativo', 'N/A')}` - {(d.get('asunto') or 'Sin asunto')[:60]}\n"
                texto += f"  📅 {d.get('fecha_documento', 'N/A')} | {d.get('estado', 'N/A')}\n"
        else:
            texto = f"📭 No se encontraron documentos con '{termino}'"
        
        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en buscar_command: {e}")
        await update.message.reply_text("❌ Error en búsqueda")


# ─────────────────────────────────────────────────────────────────
# CONSULTAS DE DOCUMENTOS (via backend / Postgres, solo lectura)
# ─────────────────────────────────────────────────────────────────

PAGE_SIZE = 8  # docs por pagina en listados (limite seguro de 4096 chars)


def _fmt_fecha(f: Optional[str]) -> str:
    """YYYY-MM-DD -> DD/MM/YYYY; '' si vacio."""
    if not f:
        return ""
    try:
        a, m, d = f.split("-")
        return f"{d}/{m}/{a}"
    except Exception:
        return str(f)


def _fmt_doc_line(d: Dict[str, Any], n: int) -> str:
    """Una linea de listado: correlativo + fecha + asunto truncado."""
    asunto = (d.get("asunto") or "Sin asunto")[:60]
    return (
        f"{n}. `{d.get('correlativo', 'N/A')}` — {_fmt_fecha(d.get('fecha_documento'))}\n"
        f"   {asunto}\n"
    )


def _filtros_clave(filtros: Dict[str, Any]) -> str:
    """Clave estable para guardar el estado de paginacion en user_data."""
    return "|".join(f"{k}={v}" for k, v in sorted(filtros.items()) if v)


async def _listar_documentos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    filtros: Dict[str, Any],
    titulo: str,
    pagina: int = 0,
    editar_mensaje=None,
):
    """Listar documentos paginados. Responde al mensaje o edita uno existente (paginacion)."""
    try:
        from bot.core.backend_client import consultar_documentos
        docs = await consultar_documentos(
            limit=PAGE_SIZE + 1,
            offset=pagina * PAGE_SIZE,
            **filtros,
        )
    except Exception as e:
        logger.error(f"listar_documentos_failed: {e}")
        if editar_mensaje:
            await editar_mensaje.edit_text("❌ El servicio no respondió, intenta de nuevo.")
        else:
            await update.message.reply_text("❌ El servicio no respondió, intenta de nuevo.")
        return

    hay_mas = len(docs) > PAGE_SIZE
    docs = docs[:PAGE_SIZE]

    if not docs and pagina == 0:
        texto = f"📭 {titulo}: no hay documentos."
        if editar_mensaje:
            await editar_mensaje.edit_text(texto)
        else:
            await update.message.reply_text(texto)
        return

    texto = f"📋 **{titulo}** — pág {pagina + 1}\n\n"
    for i, d in enumerate(docs, start=1):
        texto += _fmt_doc_line(d, pagina * PAGE_SIZE + i)
    if not hay_mas and pagina > 0:
        texto += "\n_Fin de la lista_"

    # Guardar filtros para que el callback de paginacion los recupere
    filtros_key = str(abs(hash(_filtros_clave(filtros))) % 10**8)
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    botones = []
    if pagina > 0 or hay_mas:
        fila = []
        if pagina > 0:
            fila.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"page:{pagina - 1}:{filtros_key}"))
        if hay_mas:
            fila.append(InlineKeyboardButton(f"Pág {pagina + 1} ▶️", callback_data=f"page:{pagina + 1}:{filtros_key}"))
        botones.append(fila)
    markup = InlineKeyboardMarkup(botones) if botones else None

    # user_data del usuario que consulta (via context de PTB)
    if update.effective_user is not None and hasattr(context, "user_data"):
        context.user_data.setdefault("pag_filtros", {})[filtros_key] = filtros

    if editar_mensaje:
        await editar_mensaje.edit_text(texto, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)


def _args_a_filtros(args, tipo: Optional[str] = None) -> Dict[str, Any]:
    """Construir filtros de consulta desde argumentos simples."""
    filtros: Dict[str, Any] = {}
    if tipo:
        filtros["tipo_documento"] = tipo
    return filtros


async def doc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /doc <correlativo> - Ficha completa de un documento."""
    if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
        return
    args = context.args
    if not args:
        await update.message.reply_text("Uso: `/doc <correlativo>`\nEj: `/doc OTIC-NOTA-2026-042`", parse_mode="Markdown")
        return
    correlativo = " ".join(args).strip().upper()
    try:
        from bot.core.backend_client import consultar_documentos
        docs = await consultar_documentos(search=correlativo, limit=20)
    except Exception as e:
        logger.error(f"doc_command_failed: {e}")
        await update.message.reply_text("❌ El servicio no respondió, intenta de nuevo.")
        return

    exacto = next((d for d in docs if (d.get("correlativo") or "").upper() == correlativo), None)
    if not exacto:
        if docs:
            sug = "\n".join(f"• `{d.get('correlativo')}`" for d in docs[:5])
            await update.message.reply_text(
                f"📭 No hay documento exacto `{correlativo}`.\n\n¿Quisiste decir?:\n{sug}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(f"📭 No se encontró `{correlativo}`.")
        return

    d = exacto
    anexos = d.get("anexos") or []
    texto = (
        f"📄 **{d.get('correlativo', 'N/A')}** ({d.get('tipo_doc_codigo') or d.get('tipo_documento') or '?'})\n"
        f"📅 Doc: {_fmt_fecha(d.get('fecha_documento'))} | Rec: {_fmt_fecha(d.get('fecha_recepcion'))}\n"
        f"🏢 {d.get('oficina_origen_sigla') or '?'} → {d.get('oficina_destino_sigla') or '?'}\n"
        f"📝 {d.get('asunto') or 'Sin asunto'}\n"
    )
    if d.get("remitente"):
        texto += f"👤 {d['remitente']}\n"
    if d.get("destinatario"):
        texto += f"📬 {d['destinatario']}\n"
    texto += f"📌 Estado: {d.get('estado', '?')} | Prioridad: {d.get('prioridad', 'NORMAL')}\n"
    if anexos:
        texto += "📎 Anexos: " + ", ".join(str(a) for a in anexos[:5]) + "\n"
    if d.get("folios"):
        texto += f"📄 Folios: {d['folios']}\n"
    if d.get("observaciones"):
        texto += f"💬 {(d['observaciones'] or '')[:200]}\n"
    await update.message.reply_text(texto, parse_mode="Markdown")


async def documentos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /documentos [TIPO] - Listado paginado."""
    if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
        return
    from bot.core.backend_client import TIPOS_VALIDOS
    tipo = args[0].upper() if (args := context.args) and args[0].upper() in TIPOS_VALIDOS else None
    titulo = f"Documentos — {tipo}" if tipo else "Documentos (todos)"
    filtros = {"tipo_documento": tipo} if tipo else {}
    await _listar_documentos(update, context, filtros, titulo)


def _alias_tipo(tipo: str):
    """Genera un handler de alias: /memos == /documentos MEMO."""
    async def _handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
            return
        await _listar_documentos(update, context, {"tipo_documento": tipo}, f"{tipo}s")
    return _handler


memos_command = _alias_tipo("MEMO")
notas_command = _alias_tipo("NOTA")
oficios_command = _alias_tipo("OFICIO")
informes_command = _alias_tipo("INFORME")
circulares_command = _alias_tipo("CIRCULAR")
actas_command = _alias_tipo("ACTA")


async def fecha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /fecha <fecha> [tipo] - Documentos por dia/mes/anio."""
    if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
        return
    from bot.core.backend_client import parsear_fecha, extraer_tipo
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: `/fecha <DD/MM/AAAA | MM/AAAA | AAAA> [tipo]`\n"
            "Ej: `/fecha 19/08/2026` · `/fecha 08/2026 memos`",
            parse_mode="Markdown",
        )
        return
    tipo, resto = extraer_tipo(args)
    rango = parsear_fecha(" ".join(resto))
    if not rango:
        await update.message.reply_text(
            "❌ Fecha inválida. Usa `DD/MM/AAAA`, `MM/AAAA` o `AAAA`.",
            parse_mode="Markdown",
        )
        return
    filtros = {"fecha_desde": rango[0], "fecha_hasta": rango[1]}
    if tipo:
        filtros["tipo_documento"] = tipo
    await _listar_documentos(update, context, filtros, f"Fecha {' '.join(resto)}" + (f" — {tipo}" if tipo else ""))


async def estado_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /estado <ESTADO> - Documentos por estado."""
    if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
        return
    from bot.core.backend_client import ESTADOS_VALIDOS
    args = context.args
    if not args or args[0].upper() not in ESTADOS_VALIDOS:
        await update.message.reply_text(
            "Uso: `/estado <estado>`\nEstados: " + ", ".join(ESTADOS_VALIDOS),
            parse_mode="Markdown",
        )
        return
    estado = args[0].upper()
    await _listar_documentos(update, context, {"estado": estado}, f"Estado {estado}")


async def oficina_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /oficina <SIGLA> [origen|destino] - Documentos de una oficina."""
    if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: `/oficina <SIGLA> [origen|destino]`\nEj: `/oficina OTIC` · `/oficina JUR destino`",
            parse_mode="Markdown",
        )
        return
    sigla = args[0].upper()
    modo = args[1].lower() if len(args) > 1 and args[1].lower() in ("origen", "destino") else "origen"
    filtros = {"oficina_origen": sigla} if modo == "origen" else {"oficina_destino": sigla}
    await _listar_documentos(update, context, filtros, f"Oficina {sigla} ({modo})")


async def resumen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resumen - Metricas rapidas del sistema."""
    if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            r = await client.get("http://osda-backend:8000/api/documentos/metricas")
            r.raise_for_status()
            m = r.json()
            r2 = await client.get("http://osda-backend:8000/api/documentos", params={"limit": 1})
            r2.raise_for_status()
            ultimo = (r2.json() or [{}])[0]
    except Exception as e:
        logger.error(f"resumen_command_failed: {e}")
        await update.message.reply_text("❌ El servicio no respondió, intenta de nuevo.")
        return

    por_tipo = ", ".join(f"{t['count']} {t['tipo']}" for t in (m.get("por_tipo") or [])) or "—"
    por_estado = ", ".join(f"{e['count']} {e['estado']}" for e in (m.get("por_estado") or [])) or "—"
    texto = (
        f"📊 **Resumen documental**\n\n"
        f"• Total: **{m.get('total', 0)}** documentos\n"
        f"• Por tipo: {por_tipo}\n"
        f"• Por estado: {por_estado}\n"
        f"• Este mes: {m.get('este_mes', 0)}\n"
        f"• Último registro: `{ultimo.get('correlativo', '—')}` ({_fmt_fecha(ultimo.get('fecha_documento'))})\n\n"
        f"_Usa /doc <correlativo> para ver uno, /ayuda para todo el menú._"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")


async def consulta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /consulta <pregunta> - Consultas en lenguaje natural."""
    if not is_authorized(update.effective_chat.id, update.effective_user.id, update.message.message_thread_id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: `/consulta <pregunta>`\n"
            "Ejemplos:\n"
            "• `/consulta cuantos memos faltan por registrar`\n"
            "• `/consulta cuantos oficios pendientes en OTIC`\n"
            "• `/consulta cuantos documentos registró OTIC este mes`\n"
            "• `/consulta cuantos informes archivados`\n"
            "• `/consulta cual es el ultimo correlativo de OTIC MEMO`\n",
            parse_mode="Markdown"
        )
        return

    pregunta = " ".join(args).lower()

    try:
        from bot.core.backend_client import consultar_documentos, TIPOS_VALIDOS, ESTADOS_VALIDOS
        import re
        import calendar
        from datetime import date

        # Detectar tipo de documento
        tipo = None
        for t in TIPOS_VALIDOS:
            if t.lower() in pregunta:
                tipo = t
                break

        # Detectar estado
        estado = None
        for e in ESTADOS_VALIDOS:
            if e.lower() in pregunta:
                estado = e
                break

        # Detectar intención de "último/última correlativo"
        last_correlativo_keywords = ["ultimo", "último", "ultima", "última"]
        is_last_correlativo = any(k in pregunta for k in last_correlativo_keywords) and ("correlativo" in pregunta or "correlativos" in pregunta)

        # Detectar intención de "huecos/faltantes en correlativos"
        gap_keywords = ["faltan", "faltante", "huecos", "hueco", "pendientes de registrar", "por registrar", "faltan por"]
        is_gaps = any(k in pregunta for k in gap_keywords) and ("correlativo" in pregunta or "correlativos" in pregunta or "numer" in pregunta or "numero" in pregunta or "secuencia" in pregunta or tipo in ["MEMO", "OFICIO", "CIRCULAR", "INFORME", "NOTA", "ACTA", "RESOLUCION", "SOLICITUD", "RECIBO", "OTRO"])
        
        # Si no hay tipo específico pero sí palabras de huecos, intentar detectar tipo
        if is_gaps and not tipo:
            for t in TIPOS_VALIDOS:
                if t.lower() in pregunta:
                    tipo = t
                    break

        # Detectar subtipo "nota de entrega" / "entrega" para búsqueda en asunto
        # Si preguntan "notas de entrega", "nota de entrega", "entregas" -> buscar NOTA con search="entrega"
        search_subtipo = None
        if tipo == "NOTA" and ("de entrega" in pregunta or "entregas" in pregunta or "entrega" in pregunta):
            search_subtipo = "entrega"
        elif "nota de entrega" in pregunta or "notas de entrega" in pregunta:
            # Si no se detectó tipo NOTA pero preguntan por "nota de entrega"
            tipo = "NOTA"
            search_subtipo = "entrega"

        # Detectar intención de conteo (con normalización Unicode)
        import unicodedata
        count_keywords = ["cuantos", "cuántos", "cuantas", "cuántas", "total", "numero", "número"]
        # Normalizar a NFC para comparar correctamente acentos
        pregunta_nfc = unicodedata.normalize("NFC", pregunta)
        count_keywords_nfc = [unicodedata.normalize("NFC", k) for k in count_keywords]
        is_count = any(k in pregunta_nfc for k in count_keywords_nfc)

        # Detectar filtros temporales
        fecha_desde = None
        fecha_hasta = None
        mes_actual = False
        if "este mes" in pregunta or "mes actual" in pregunta:
            hoy = date.today()
            inicio_mes = date(hoy.year, hoy.month, 1).isoformat()
            fin_mes = date(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1]).isoformat()
            fecha_desde = inicio_mes
            fecha_hasta = fin_mes
            mes_actual = True

        # Obtener lista de oficinas del backend para detectar siglas en la pregunta
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            resp = await client.get("http://osda-backend:8000/api/oficinas")
            resp.raise_for_status()
            oficinas = resp.json()
        oficinas_siglas = [o["sigla"].lower() for o in oficinas if o.get("activa")]

        # Mapeo de nombres comunes/alias a siglas para consultas en lenguaje natural
        import unicodedata
        def _normalize(s: str) -> str:
            """Normalizar: minúsculas + quitar acentos (NFD + remover marcas)"""
            return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))
        
        OFICINA_ALIASES = {}
        for o in oficinas:
            if not o.get("activa"):
                continue
            sigla = o["sigla"].upper()
            nombre = o.get("nombre", "")
            # Agregar sigla normalizada
            OFICINA_ALIASES[_normalize(sigla)] = sigla
            # Agregar nombre completo normalizado
            if nombre:
                OFICINA_ALIASES[_normalize(nombre)] = sigla
            # Agregar palabras clave del nombre normalizadas
            palabras_nombre = nombre.split()
            for palabra in palabras_nombre:
                if len(palabra) > 3:  # Solo palabras significativas
                    OFICINA_ALIASES[_normalize(palabra)] = sigla

        # Detectar si la pregunta tiene relación con documentos
        # Palabras clave relacionadas con documentos
        DOCUMENT_KEYWORDS = TIPOS_VALIDOS + ESTADOS_VALIDOS + [
            "cuantos", "cuántos", "cuantas", "cuántas", "total", "numero", "número",
            "documento", "documentos", "memo", "memos", "oficio", "oficios",
            "correlativo", "correlativos", "pendiente", "pendientes",
            "registrado", "registrados", "archivado", "archivados",
            "recibido", "respondido", "tramite", "trámite",
            "este mes", "mes actual", "ultimo", "último", "ultima", "última",
        ]
        DOCUMENT_KEYWORDS.extend(oficinas_siglas)
        DOCUMENT_KEYWORDS.extend(OFICINA_ALIASES.keys())

        # Verificar si la pregunta tiene al menos una palabra clave de documentos
        es_consulta_documentos = any(kw in pregunta for kw in DOCUMENT_KEYWORDS)

        if not es_consulta_documentos:
            await update.message.reply_text(
                "🤖 **Solo consultas relacionadas con documentos**\n\n"
                "Este bot está diseñado para consultar información sobre documentos, "
                "memos, oficios, correlativos, estados, oficinas, etc.\n\n"
                "**Ejemplos de lo que puedo hacer:**\n"
                "• `/consulta cuantos memos para OGH`\n"
                "• `/consulta cuantos oficios pendientes en OTIC`\n"
                "• `/consulta cuantos documentos de JUR este mes`\n"
                "• `/consulta cual es el ultimo correlativo de OTIC MEMO`\n"
                "• `/consulta cuantos informes archivados`\n\n"
                "Para otras consultas, por favor contacta al administrador.",
                parse_mode="Markdown"
            )
            return

        # Detectar oficina (sigla o alias) en la pregunta
        oficina = None
        oficina_destino = None
        
        # Normalizar pregunta para matching (quitar acentos)
        pregunta_norm = _normalize(pregunta)
        
        # Primero buscar por alias (nombres completos y palabras clave)
        # Ordenar por longitud descendente para coincidir frases más largas primero
        sorted_aliases = sorted(OFICINA_ALIASES.items(), key=lambda x: -len(x[0]))
        for alias, sigla in sorted_aliases:
            # alias ya está normalizado
            if f" {alias} " in f" {pregunta_norm} " or pregunta_norm.startswith(f"{alias} ") or pregunta_norm.endswith(f" {alias}"):
                # Check for destination patterns
                if f"para {alias}" in pregunta_norm or f"a {alias}" in pregunta_norm:
                    if not oficina_destino:  # Only set if not already found
                        oficina_destino = sigla
                # Check for origin patterns
                elif f"de {alias}" in pregunta_norm or f"desde {alias}" in pregunta_norm:
                    if not oficina:  # Only set if not already found
                        oficina = sigla
                # Default to origin if no specific pattern and no origin yet
                elif not oficina:
                    oficina = sigla
        
        # Si no se encontró por alias, buscar por sigla directa
        if not oficina and not oficina_destino:
            for sigla in oficinas_siglas:
                if f" {sigla} " in f" {pregunta} " or pregunta.startswith(f"{sigla} ") or pregunta.endswith(f" {sigla}"):
                    if f"para {sigla}" in pregunta or f"a {sigla}" in pregunta:
                        oficina_destino = sigla.upper()
                    elif f"de {sigla}" in pregunta or f"desde {sigla}" in pregunta:
                        oficina = sigla.upper()
                    elif not oficina:
                        oficina = sigla.upper()
                    break

        # Ejecutar consulta según intención
        filtros = {}
        if tipo:
            filtros["tipo_documento"] = tipo
        if estado:
            filtros["estado"] = estado
        if oficina:
            filtros["oficina_origen"] = oficina
        if oficina_destino:
            filtros["oficina_destino"] = oficina_destino
        if fecha_desde:
            filtros["fecha_desde"] = fecha_desde
        if fecha_hasta:
            filtros["fecha_hasta"] = fecha_hasta
        if search_subtipo:
            filtros["search"] = search_subtipo

        # Para último correlativo: ordenar por fecha descendente y límite 1
        if is_last_correlativo:
            filtros["order"] = "fecha_documento.desc"
            docs = await consultar_documentos(**filtros, limit=1)

            # Filtrar adicionales en Python para consultas complejas
            if mes_actual:
                hoy = date.today()
                docs = [d for d in docs if d.get("fecha_documento", "").startswith(f"{date.today().year}-{date.today().month:02d}")]

            respuesta = f"📊 **Consulta: {' '.join(args)}**\n\n"
            respuesta += f"📊 **Total: {len(docs)}**"
            if tipo:
                respuesta += f" {tipo}"
            if estado:
                respuesta += f" {estado}"
            if mes_actual:
                respuesta += " este mes"
            respuesta += "\n"

            # Agregar desglose si hay pocos resultados
            if len(docs) <= 20:
                respuesta += "\n*Detalle:*\n"
                for d in docs[:10]:
                    respuesta += f"• `{d.get('correlativo', 'N/A')}` - {d.get('asunto', 'Sin asunto')[:50]}\n"
                if len(docs) > 10:
                    respuesta += f"... y {len(docs) - 10} más"

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

        # Para consultas de huecos/faltantes en correlativos
        if is_gaps:
            if not oficina:
                respuesta = "❌ Necesitas especificar una oficina (ej: OTIC, OGH, Presidencia, etc.)"
                await update.message.reply_text(respuesta, parse_mode="Markdown")
                return
            if not tipo:
                respuesta = "❌ Necesitas especificar un tipo de documento (MEMO, OFICIO, INFORME, NOTA, etc.)"
                await update.message.reply_text(respuesta, parse_mode="Markdown")
                return
            
            from bot.core.backend_client import detectar_huecos_correlativo
            resultado = await detectar_huecos_correlativo(oficina, tipo)
            
            if resultado["total_registrados"] == 0:
                respuesta = f"📭 No hay {tipo}s registrados para {oficina}"
            else:
                huecos = resultado["huecos"]
                respuesta = f"🔍 **Huecos en correlativos {tipo} - {oficina}**\n\n"
                respuesta += f"📋 Registrados: {resultado['total_registrados']}\n"
                respuesta += f"🔢 Máximo secuencia: {resultado['max_secuencia']}\n"
                respuesta += f"❌ Faltantes: {len(huecos)}\n\n"
                
                if huecos:
                    respuesta += f"📋 **Correlativos faltantes:**\n"
                    # Mostrar los huecos como correlativos completos
                    # Necesitamos saber el formato: OTIC-MEMO-2026-XXX
                    # Usamos el año actual y el formato detectado
                    hoy = date.today()
                    anio = str(hoy.year)
                    # Detectar prefijo del primer correlativo registrado
                    primer_corr = resultado["correlativos_registrados"][0] if resultado["correlativos_registrados"] else ""
                    prefijo = ""
                    if primer_corr:
                        # Extraer todo antes del último número
                        import re
                        match = re.match(r'^(.+-\d{4}-)', primer_corr)
                        if match:
                            prefijo = match.group(1)
                    
                    for h in huecos[:20]:
                        if prefijo:
                            respuesta += f"• `{prefijo}{h:03d}`\n"
                        else:
                            respuesta += f"• Secuencia `{h}`\n"
                    if len(huecos) > 20:
                        respuesta += f"... y {len(huecos) - 20} más\n"
                else:
                    respuesta += "✅ No hay huecos en la numeración."
            
            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

        # Para consultas de conteo: usar return_count=True para obtener total del backend
        if is_count:
            docs, total = await consultar_documentos(**filtros, limit=1000, return_count=True)

            respuesta = f"📊 **Consulta: {' '.join(args)}**\n\n"
            respuesta += f"📊 **Total: {total}**"
            if tipo:
                respuesta += f" {tipo}"
            if estado:
                respuesta += f" {estado}"
            if oficina:
                respuesta += f" de {oficina}"
            if oficina_destino:
                respuesta += f" para {oficina_destino}"
            if mes_actual:
                respuesta += " este mes"
            respuesta += "\n"

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

        # Consulta de listado normal
        await _listar_documentos(update, context, filtros, f"Consulta: {' '.join(args)}")

    except Exception as e:
        logger.error(f"Error en consulta_command: {e}")
        await update.message.reply_text("❌ Error procesando consulta")


async def huecos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /huecos <oficina> <tipo> - Detectar huecos en numeración de correlativos.
    
    Ej: /huecos OTIC MEMO
    Detecta números faltantes en la secuencia (ej: si hay 1,2,4,5 -> falta el 3)
    """
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: `/huecos <oficina> <tipo>`\n"
            "Ej: `/huecos OTIC MEMO`\n"
            "Detecta números faltantes en la secuencia de correlativos.",
            parse_mode="Markdown"
        )
        return
    
    oficina, tipo = args[0].upper(), args[1].upper()
    
    # Validar tipo
    from bot.core.backend_client import TIPOS_VALIDOS
    if tipo not in TIPOS_VALIDOS:
        await update.message.reply_text(
            f"❌ Tipo inválido. Tipos válidos: {', '.join(TIPOS_VALIDOS)}",
            parse_mode="Markdown"
        )
        return
    
    try:
        from bot.core.backend_client import detectar_huecos_correlativo
        
        await update.message.reply_text(f"🔍 Analizando huecos en {oficina} - {tipo}...")
        
        resultado = await detectar_huecos_correlativo(oficina, tipo)
        
        total = resultado["total_registrados"]
        max_seq = resultado["max_secuencia"]
        huecos = resultado["huecos"]
        correlativos = resultado["correlativos_registrados"]
        
        if total == 0:
            await update.message.reply_text(
                f"📭 No hay correlativos registrados para {oficina} - {tipo}",
                parse_mode="Markdown"
            )
            return
        
        texto = f"🔍 **Análisis de huecos: {oficina} - {tipo}**\n\n"
        texto += f"📊 Total registrados: **{total}**\n"
        texto += f"🔢 Secuencia máxima: **{max_seq}**\n\n"
        
        if huecos:
            texto += f"⚠️ **Huecos detectados ({len(huecos)}):**\n"
            # Mostrar en grupos de 20 para no saturar
            for i, h in enumerate(huecos):
                if i < 50:
                    texto += f"• Falta: **{h}** (correlativo {oficina}-{tipo}-{h:03d})\n"
                elif i == 50:
                    texto += f"... y {len(huecos) - 50} huecos más\n"
                    break
            texto += f"\n💡 *Total faltantes: {len(huecos)} de {max_seq} esperados*"
        else:
            texto += f"✅ **Sin huecos** - Secuencia completa del 1 al {max_seq}\n"
        
        # Mostrar últimos 5 correlativos registrados
        if correlativos:
            texto += f"\n📋 **Últimos registrados:**\n"
            for c in correlativos[-5:]:
                texto += f"• `{c}`\n"
        
        await update.message.reply_text(texto, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error en huecos_command: {e}")
        await update.message.reply_text("❌ Error analizando huecos")


async def paginacion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback de botones de paginacion: page:<pagina>:<filtros_key>. (answer ya hecho arriba)"""
    query = update.callback_query
    data = query.data
    try:
        _, pagina_s, filtros_key = data.split(":", 2)
        pagina = int(pagina_s)
    except Exception:
        await query.edit_message_text("❌ Acción expirada.")
        return
    store = context.user_data if context is not None else {}
    filtros = (store.get("pag_filtros") or {}).get(filtros_key)
    if filtros is None:
        await query.edit_message_text("❌ La consulta expiró. Vuelve a ejecutar el comando.")
        return
    await _listar_documentos(update, context, filtros, "Resultados", pagina=pagina, editar_mensaje=query.message)


# ─────────────────────────────────────────────────────────────────
# DOCUMENT PROCESSING
# ─────────────────────────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar documento recibido (foto o archivo)."""
    message = update.message
    thread_id = message.message_thread_id
    
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        return  # Silencioso: no responde en topics no autorizados
    
    # Determinar file_id y mime_type
    if message.photo:
        file_id = message.photo[-1].file_id  # Mayor resolución
        mime_type = "image/jpeg"
        file_name = f"photo_{file_id}.jpg"
    elif message.document:
        file_id = message.document.file_id
        mime_type = message.document.mime_type or "application/octet-stream"
        file_name = message.document.file_name or f"doc_{file_id}"
        
        # Validar tipo
        allowed = settings.ALLOWED_MIME_TYPES.split(",")
        if mime_type not in allowed:
            await message.reply_text(
                f"❌ Tipo de archivo no soportado: {mime_type}\n"
                f"Formatos permitidos: {', '.join(allowed)}"
            )
            return
    else:
        return
    
    # Mensaje de procesando (best-effort: si Telegram tarda, NO abortar el documento)
    try:
        status_msg = await message.reply_text("📥 Descargando archivo...")
    except Exception as e:
        logger.warning(f"No se pudo enviar mensaje de estado inicial: {e}")
        status_msg = None
    
    # LOG: Capturar thread_id para debugging
    thread_id = message.message_thread_id
    logger.info(f"Received document in chat {update.effective_chat.id}, thread_id: {thread_id}")

    async def _estado(texto: str):
        """Editar el mensaje de estado sin que un fallo mate el flujo."""
        if status_msg is None:
            return
        try:
            await status_msg.edit_text(texto)
        except Exception as e:
            logger.warning(f"edit_text de estado fallo (no aborto): {e}")

    try:
        # Descargar archivo
        file = await context.bot.get_file(file_id)
        
        import tempfile
        import os
        
        # Crearchivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
            temp_path = tmp.name
        
        await file.download_to_drive(temp_path)

        await _estado("🔍 Procesando con Vision API (puede tardar 1-3 min en CPU)...")

        # Procesar con Vision OCR - con callback de progreso
        import asyncio
        # Import here to ensure PYTHONPATH is set
        from app.services.vision_ocr import process_document_vision
        
        # Crear task para el OCR
        ocr_task = asyncio.create_task(process_document_vision(temp_path, mime_type))

        # Mostrar progreso cada 30 segundos
        progress_dots = 0
        while not ocr_task.done():
            await asyncio.sleep(30)
            progress_dots = (progress_dots + 1) % 4
            dots = "." * progress_dots
            await _estado(f"🔍 Procesando con Vision API{dots} (CPU only, puede tardar varios minutos)")

        result = await ocr_task

        # Limpiar archivo temporal
        try:
            os.unlink(temp_path)
        except:
            pass

        if not result["success"]:
            await _estado(
                f"❌ **Error procesando documento**\n\n"
                f"{result.get('error', 'Error desconocido')}\n\n"
                f"Por favor, envíe una foto más nítida del documento completo."
            )
            return

        # Guardar en contexto para validación
        import hashlib
        doc_key = hashlib.md5(f"{file_id}_{update.effective_user.id}".encode()).hexdigest()[:16]
        context.bot_data[doc_key] = {
            "file_id": file_id,
            "file_path": temp_path,  # Ya no existe, pero guardamos info
            "mime_type": mime_type,
            "ocr_data": result["data"],
            "chat_id": update.effective_chat.id,
            "user_id": update.effective_user.id,
            "telegram_user_id": update.effective_user.id,
            "message_id": status_msg.message_id if status_msg else None,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Mostrar preview con botones (aqui SI importa que llegue: reintentos)
        preview_text = format_ocr_preview(result["data"], result["confidence"])
        keyboard = get_validation_keyboard(doc_key)

        if status_msg is not None:
            for intento in range(3):
                try:
                    await status_msg.edit_text(
                        preview_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    break
                except Exception as e:
                    logger.warning(f"edit_text del preview fallo (intento {intento + 1}/3): {e}")
                    await asyncio.sleep(3)
            else:
                # El preview no se pudo editar: avisar en mensaje nuevo
                logger.error("No se pudo mostrar el preview; el documento SI fue procesado")
                try:
                    await message.reply_text(
                        f"✅ Documento procesado (correlativo detectado: {result['data'].get('correlativo', '?')}).\n"
                        f"⚠️ No se pudo mostrar el menú de validación: responde a ESTE mensaje con 'ok' para aprobarlo.",
                    )
                except Exception:
                    pass
        else:
            try:
                await message.reply_text(
                    preview_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"No se pudo enviar el preview en mensaje nuevo: {e}")

    except Exception as e:
        logger.error(f"Error en handle_document: {e}")
        await _estado(f"❌ Error procesando documento: {e}")


# ─────────────────────────────────────────────────────────────────
# VALIDATION CALLBACKS
# ─────────────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejar botones inline de validación."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split(":", 2)
    action = parts[0]
    doc_key = parts[1] if len(parts) > 1 else ""

    # Paginacion de listados de consulta (no depende de documentos pendientes)
    if action == "page":
        await paginacion_callback(update, context)
        return

    if doc_key not in context.bot_data:
        await query.edit_message_text("❌ Documento no encontrado o expirado.")
        return
    
    pending = context.bot_data[doc_key]
    
    # Verificar autorización
    if query.from_user.id != pending["user_id"]:
        await query.answer("❌ Solo quien envió el documento puede validarlo.", show_alert=True)
        return
    
    if action == "approve":
        await approve_document(query, pending, doc_key, context)
    elif action == "correct":
        await start_correction(query, pending, doc_key, context)
    elif action == "reject":
        await reject_document(query, pending, doc_key, context)
    elif action == "edit":
        field = parts[2] if len(parts) > 2 else ""
        await edit_field(query, pending, doc_key, field, context)
    elif action == "finish_edit":
        await finish_correction(query, pending, doc_key, context)
    elif action == "cancel_edit":
        await cancel_correction(query, pending, doc_key, context)


async def approve_document(query, pending: dict, doc_key: str, context: ContextTypes.DEFAULT_TYPE):
    """Aprobar y guardar documento."""
    await query.edit_message_text("✅ Guardando documento...")
    
    try:
        ocr_data = pending["ocr_data"]
        
        # Llamar al backend API para guardar el documento
        import httpx
        from bot.core.config import settings
        
        # Preparar datos para el backend
        doc_data = {
            "correlativo": ocr_data.get("correlativo"),
            "tipo_doc_codigo": ocr_data.get("tipo_documento"),
            "oficina_origen_sigla": ocr_data.get("oficina_origen"),
            "oficina_destino_sigla": ocr_data.get("oficina_destino"),
            "fecha_documento": ocr_data.get("fecha_documento"),
            "fecha_recepcion": ocr_data.get("fecha_recepcion"),
            "remitente": ocr_data.get("remitente"),
            "destinatario": ocr_data.get("destinatario"),
            "asunto": ocr_data.get("asunto"),
            "folios": ocr_data.get("folios"),
            "anexos": ocr_data.get("anexos", []),
            "observaciones": ocr_data.get("observaciones"),
            "prioridad": "NORMAL",
            "estado": "RECIBIDO",
        }
        
        # Agregar telegram_user_id si está disponible en pending
        if "telegram_user_id" in pending:
            doc_data["telegram_user_id"] = pending["telegram_user_id"]
        
        headers = {
            "Content-Type": "application/json",
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            result = await client.post(
                "http://osda-backend:8000/api/documentos",
                json=doc_data,
                headers=headers
            )
            
            # Manejar error 409 (duplicado)
            if result.status_code == 409:
                error_detail = result.json().get("detail", "Documento duplicado")
                await query.edit_message_text(
                    f"⚠️ **Documento ya registrado**\n\n"
                    f"{error_detail}\n\n"
                    f"El documento con correlativo `{ocr_data.get('correlativo', 'N/A')}` ya existe en el sistema."
                )
                return
            
            result.raise_for_status()
            created = result.json()
            
        # Respuesta exitosa
        await query.edit_message_text(
            f"✅ **Documento registrado exitosamente**\n\n"
            f"🔢 Correlativo: `{ocr_data.get('correlativo', 'N/A')}`\n"
            f"📋 Tipo: {ocr_data.get('tipo_documento', 'N/A')}\n"
            f"🏢 {ocr_data.get('oficina_origen', 'N/A')} → {ocr_data.get('oficina_destino', 'N/A')}\n"
            f"📅 Fecha: {ocr_data.get('fecha_documento', 'N/A')}\n"
            f"📝 Estado: RECIBIDO\n"
            f"🆔 ID: `{created.get('id', 'N/A')}`"
        )
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP aprobando documento: {e}, response: {e.response.text}")
        # Manejar error 409 específicamente
        if e.response.status_code == 409:
            error_detail = e.response.json().get("detail", "Documento duplicado")
            await query.edit_message_text(
                f"⚠️ **Documento ya registrado**\n\n"
                f"{error_detail}\n\n"
                f"El documento con correlativo `{ocr_data.get('correlativo', 'N/A')}` ya existe en el sistema."
            )
        else:
            await query.edit_message_text(f"❌ Error guardando: {e.response.text[:200]}")
    except Exception as e:
        logger.error(f"Error aprobando documento: {e}")
        await query.edit_message_text(f"❌ Error guardando: {str(e)[:200]}")
    finally:
        # Limpiar
        if doc_key in context.bot_data:
            del context.bot_data[doc_key]


async def show_correction_menu(target, context: ContextTypes.DEFAULT_TYPE, pending: dict, doc_key: str):
    """Mostrar menú de corrección (reutilizable)."""
    ocr_data = pending["ocr_data"]
    
    keyboard = []
    fields = [
        ("correlativo", "🔢 Correlativo"),
        ("fecha_documento", "📅 Fecha documento"),
        ("fecha_recepcion", "📥 Fecha recepción"),
        ("remitente", "👤 Remitente"),
        ("destinatario", "👥 Destinatario"),
        ("oficina_origen", "🏢 Oficina origen"),
        ("oficina_destino", "🏢 Oficina destino"),
        ("tipo_documento", "📋 Tipo"),
        ("asunto", "📝 Asunto"),
        ("folios", "📄 Folios"),
    ]
    
    for field_key, field_label in fields:
        current = ocr_data.get(field_key, "No detectado")
        keyboard.append([
            InlineKeyboardButton(
                f"{field_label}: {current}"[:60],
                callback_data=f"edit:{doc_key}:{field_key}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("✅ Terminar corrección", callback_data=f"finish_edit:{doc_key}")])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data=f"reject:{doc_key}")])
    
    text = "✏️ **Corrección de campos**\n\nSeleccione el campo a corregir:"
    markup = InlineKeyboardMarkup(keyboard)
    
    # Manejar tanto CallbackQuery como Message
    if hasattr(target, 'edit_message_text'):
        # Es un CallbackQuery
        await target.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    elif hasattr(target, 'message') and hasattr(target.message, 'reply_text'):
        # Es un Update con message
        await target.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    elif hasattr(target, 'reply_text'):
        # Es un Message directo
        await target.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        # Fallback: intentar reply_text
        await target.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def start_correction(query, pending: dict, doc_key: str, context: ContextTypes.DEFAULT_TYPE):
    """Iniciar corrección de campos."""
    await show_correction_menu(query, context, pending, doc_key)


async def reject_document(query, pending: dict, doc_key: str, context: ContextTypes.DEFAULT_TYPE):
    """Rechazar documento."""
    await query.edit_message_text(
        "❌ **Documento rechazado**\n\n"
        "Por favor, envíe una foto más nítida del documento completo."
    )
    
    if doc_key in context.bot_data:
        del context.bot_data[doc_key]


async def edit_field(query, pending: dict, doc_key: str, field: str, context: ContextTypes.DEFAULT_TYPE):
    """Editar un campo específico."""
    # Guardar campo en edición
    context.user_data[CORRECTION_FIELD] = field
    
    field_labels = {
        "correlativo": "🔢 Correlativo (ej: OTIC-MEMO-2026-0001)",
        "fecha_documento": "📅 Fecha documento (YYYY-MM-DD)",
        "fecha_recepcion": "📥 Fecha recepción (YYYY-MM-DD)",
        "remitente": "👤 Remitente (nombre y cargo)",
        "destinatario": "👥 Destinatario (nombre y cargo)",
        "oficina_origen": "🏢 Oficina origen (sigla: OTIC, OGA, DP...)",
        "oficina_destino": "🏢 Oficina destino (sigla: OTIC, OGA, DP...)",
        "tipo_documento": "📋 Tipo (MEMO, OFICIO, CIRCULAR, INFORME, NOTA, ACTA, RESOLUCION, SOLICITUD, RECIBO, OTRO)",
        "asunto": "📝 Asunto / Referencia",
        "folios": "📄 Folios (número entero)",
    }
    
    await query.edit_message_text(
        f"✏️ **Editando: {field_labels.get(field, field)}**\n\n"
        f"Escriba el nuevo valor:",
        parse_mode="Markdown"
    )
    
    # Marcar que esperamos texto
    context.user_data["awaiting_correction"] = True


async def handle_correction_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejar texto de corrección."""
    if not context.user_data.get("awaiting_correction"):
        return
    
    field = context.user_data.get(CORRECTION_FIELD)
    new_value = update.message.text.strip()
    
    if not field:
        await update.message.reply_text("❌ Error: no hay campo en edición")
        return
    
    # Validar según campo
    validated_value = validate_field(field, new_value)
    if validated_value is None:
        await update.message.reply_text(f"❌ Valor inválido para {field}. Intente de nuevo.")
        return
    
    # Actualizar en bot_data (buscar doc_key del usuario)
    doc_key = None
    for key, data in context.bot_data.items():
        if data.get("user_id") == update.effective_user.id:
            doc_key = key
            break
    
    if doc_key and doc_key in context.bot_data:
        context.bot_data[doc_key]["ocr_data"][field] = validated_value
        # Escape Markdown special characters
        safe_field = field.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
        safe_value = str(validated_value).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
        await update.message.reply_text(f"✅ Campo **{safe_field}** actualizado a: `{safe_value}`", parse_mode="Markdown")
        
        # Mostrar menú de corrección nuevamente para continuar editando o terminar
        pending = context.bot_data[doc_key]
        await show_correction_menu(update, context, pending, doc_key)
    else:
        await update.message.reply_text("❌ No se encontró documento en edición")
    
    context.user_data["awaiting_correction"] = False
    context.user_data.pop(CORRECTION_FIELD, None)


def validate_field(field: str, value: str):
    """Validar valor según campo."""
    if field in ["correlativo"]:
        # Formatos reales usados por la oficina (secuencia de 3+ digitos al final):
        #   OTIC-2026-003          -> SIGLA-AÑO-SECUENCIA
        #   OTIC-MEMO-2026-042     -> SIGLA-TIPO-AÑO-SECUENCIA
        # Se normaliza a mayusculas y sin espacios antes de validar.
        v = value.strip().upper()
        if re.match(r'^[A-Z]{2,6}(-[A-Z]{2,8})?-\d{4}-\d{1,6}$', v):
            return v
        return None
    
    elif field in ["fecha_documento", "fecha_recepcion"]:
        # Formato YYYY-MM-DD
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            return None
    
    elif field in ["folios"]:
        # Número entero
        try:
            return int(value)
        except ValueError:
            return None
    
    # Para el resto, devolver el valor limpio
    return value.strip()


async def finish_correction(query, pending: dict, doc_key: str, context: ContextTypes.DEFAULT_TYPE):
    """Terminar corrección y volver a preview."""
    # Eliminar flag de corrección
    context.user_data.pop("awaiting_correction", None)
    context.user_data.pop(CORRECTION_FIELD, None)
    
    # Mostrar preview actualizado
    from bot.handlers.telegram_handlers import format_ocr_preview, get_validation_keyboard
    preview_text = format_ocr_preview(pending["ocr_data"], pending.get("confidence", 0))
    keyboard = get_validation_keyboard(doc_key)
    
    await query.edit_message_text(
        preview_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def cancel_correction(query, pending: dict, doc_key: str, context: ContextTypes.DEFAULT_TYPE):
    """Cancelar corrección y volver a preview."""
    # Eliminar flag de corrección
    context.user_data.pop("awaiting_correction", None)
    context.user_data.pop(CORRECTION_FIELD, None)
    
    # Mostrar preview actualizado
    from bot.handlers.telegram_handlers import format_ocr_preview, get_validation_keyboard
    preview_text = format_ocr_preview(pending["ocr_data"], pending.get("confidence", 0))
    keyboard = get_validation_keyboard(doc_key)
    
    await query.edit_message_text(
        preview_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


def format_ocr_preview(ocr_data: dict, confidence: float) -> str:
    """Formatear preview del OCR para validación."""
    texto = (
        f"📄 **Validar documento** (confianza: {confidence:.0%})\n\n"
        f"🔢 Correlativo: `{ocr_data.get('correlativo', 'No detectado')}`\n"
        f"📋 Tipo: {ocr_data.get('tipo_documento', 'No detectado')}\n"
        f"🏢 {ocr_data.get('oficina_origen', '?')} → {ocr_data.get('oficina_destino', '?')}\n"
        f"📅 Fecha: {ocr_data.get('fecha_documento', 'No detectada')} | Rec: {ocr_data.get('fecha_recepcion', 'No detectada')}\n"
        f"👤 Remitente: {ocr_data.get('remitente', 'No detectado')}\n"
        f"👥 Destinatario: {ocr_data.get('destinatario', 'No detectado')}\n"
        f"📝 Asunto: {ocr_data.get('asunto', 'No detectado')}\n"
        f"📄 Folios: {ocr_data.get('folios', 'No detectado')}\n"
    )
    if ocr_data.get("anexos"):
        texto += f"📎 Anexos: {', '.join(map(str, ocr_data['anexos'][:5]))}\n"
    if ocr_data.get("observaciones"):
        texto += f"💬 {(ocr_data['observaciones'] or '')[:200]}\n"
    return texto


def get_validation_keyboard(doc_key: str):
    """Teclado inline para validación."""
    keyboard = [
        [InlineKeyboardButton("✅ Aprobar", callback_data=f"approve:{doc_key}")],
        [InlineKeyboardButton("✏️ Corregir", callback_data=f"correct:{doc_key}")],
        [InlineKeyboardButton("❌ Rechazar", callback_data=f"reject:{doc_key}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def is_authorized(chat_id, user_id, thread_id):
    """Verificar autorización: solo permitir en el topic/thread configurado."""
    settings = get_settings_instance()
    
    # Si no hay topic ID configurado, permitir todos (compatibilidad)
    if not settings.TELEGRAM_DOCUMENT_TOPIC_ID:
        return True
    
    # Si no hay thread_id en el mensaje, no autorizar (es un grupo con topics)
    if thread_id is None:
        return False
    
    # Verificar que el thread_id coincida con el configurado
    try:
        allowed_thread_id = int(settings.TELEGRAM_DOCUMENT_TOPIC_ID)
        return thread_id == allowed_thread_id
    except (ValueError, TypeError):
        # Si no es un entero válido, permitir por seguridad
        return True