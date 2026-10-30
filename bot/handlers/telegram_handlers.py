"""
Telegram Bot Handlers for document processing workflow.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.core.config import settings, get_settings_instance
from app.services.vision_ocr import process_document_vision
from app.services.graphify_client import graphify_client

logger = logging.getLogger(__name__)

# Estados de conversación para corrección
CORRECTION_FIELD = "correction_field"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Bienvenida."""
    thread_id = update.message.message_thread_id
    if not is_authorized(update.effective_chat.id, update.effective_user.id, thread_id):
        await update.message.reply_text("❌ No autorizado. Contacte al administrador.")
        return
    
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
    await _listar_documentos(update, {"estado": estado}, f"Estado {estado}")


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
        if thread_id:
            await message.reply_text("❌ Este bot solo procesa documentos en el topic configurado.")
        else:
            await message.reply_text("❌ No autorizado o topic incorrecto.")
        return
    
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
    
    elif field == "folios":
        try:
            n = int(value)
            if n > 0:
                return n
            return None
        except ValueError:
            return None
    
    elif field == "tipo_documento":
        valid_types = ["MEMO", "OFICIO", "CIRCULAR", "INFORME", "NOTA", "ACTA", "RESOLUCION", "SOLICITUD", "RECIBO", "OTRO"]
        if value.upper() in valid_types:
            return value.upper()
        return None
    
    elif field in ["oficina_origen", "oficina_destino"]:
        # Permitir cualquier código de 2-10 caracteres alfanuméricos mayúsculos
        # La validación real la hace la BD con foreign key
        if re.match(r'^[A-Z0-9]{2,10}$', value.upper()):
            return value.upper()
        return None
    
    # Para texto libre
    return value if value else None


async def finish_correction(query, pending: dict, doc_key: str, context: ContextTypes.DEFAULT_TYPE):
    """Terminar corrección y mostrar preview actualizado."""
    ocr_data = pending["ocr_data"]
    
    # Recalcular confianza (simplificado)
    confidence = 0.9  # Asumimos alta tras corrección manual
    
    preview_text = format_ocr_preview(ocr_data, confidence)
    keyboard = get_validation_keyboard(doc_key)
    
    await query.edit_message_text(
        preview_text + "\n\n✏️ *Correcciones aplicadas*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def cancel_correction(query, pending: dict, doc_key: str, context: ContextTypes.DEFAULT_TYPE):
    """Cancelar corrección y volver al preview."""
    ocr_data = pending["ocr_data"]
    confidence = pending.get("confidence", 0.5)
    
    preview_text = format_ocr_preview(ocr_data, confidence)
    keyboard = get_validation_keyboard(doc_key)
    
    await query.edit_message_text(
        preview_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────

def is_authorized(chat_id: int, user_id: int, message_thread_id: int | None = None) -> bool:
    """Verificar si el chat/usuario está autorizado y si está en el topic correcto."""
    settings = get_settings_instance()
    allowed_chats = settings.TELEGRAM_ALLOWED_CHAT_IDS.split(",")
    if str(chat_id) in allowed_chats or chat_id in [int(x) for x in allowed_chats if x]:
        # Si hay topic configurado, verificar que el mensaje venga de ese topic
        if settings.TELEGRAM_DOCUMENT_TOPIC_ID:
            topic_id = int(settings.TELEGRAM_DOCUMENT_TOPIC_ID)
            # Si es un topic (forum), message_thread_id debe coincidir
            # Si no es topic (chat normal), message_thread_id será None
            if message_thread_id is not None:
                return message_thread_id == topic_id
            else:
                # Si hay topic configurado pero el mensaje no tiene thread_id, no procesar
                return False
        return True
    return False


def format_ocr_preview(ocr: dict, confidence: float) -> str:
    """Formatear vista previa de datos OCR."""
    lines = ["📄 **Datos extraídos (OCR):**", ""]
    
    fields = [
        ("🔢 Correlativo", ocr.get("correlativo")),
        ("📅 Fecha documento", ocr.get("fecha_documento")),
        ("📥 Fecha recepción", ocr.get("fecha_recepcion")),
        ("👤 Remitente", ocr.get("remitente")),
        ("👥 Destinatario", ocr.get("destinatario")),
        ("🏢 Oficina origen", ocr.get("oficina_origen")),
        ("🏢 Oficina destino", ocr.get("oficina_destino")),
        ("📋 Tipo", ocr.get("tipo_documento")),
        ("📝 Asunto", ocr.get("asunto")),
        ("📄 Folios", str(ocr.get("folios")) if ocr.get("folios") else None),
        ("📎 Anexos", ", ".join(ocr.get("anexos", [])) if ocr.get("anexos") else None),
        ("💬 Observaciones", ocr.get("observaciones")),
    ]
    
    for label, value in fields:
        if value:
            lines.append(f"{label}: `{value}`")
        else:
            lines.append(f"{label}: ❌ *No detectado*")
    
    lines.append("")
    lines.append(f"🎯 **Confianza: {confidence:.0%}**")
    
    if confidence >= 0.85:
        lines.append("✅ *Alta confianza - Listo para aprobar*")
    elif confidence >= 0.50:
        lines.append("⚠️ *Confianza media - Revisar campos*")
    else:
        lines.append("🔴 *Baja confianza - Requiere corrección manual*")
    
    return "\n".join(lines)


def get_validation_keyboard(doc_key: str) -> InlineKeyboardMarkup:
    """Crear teclado inline para validación."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Aprobar", callback_data=f"approve:{doc_key}"),
            InlineKeyboardButton("✏️ Corregir", callback_data=f"correct:{doc_key}"),
        ],
        [
            InlineKeyboardButton("❌ Rechazar", callback_data=f"reject:{doc_key}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


import re
from datetime import datetime