"""
Telegram Bot Main Entry Point.
"""
import argparse
import asyncio
import logging
import sys

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram import Update

from bot.core.config import get_settings_instance
from bot.handlers.telegram_handlers import (
    start_command,
    ayuda_command,
    oficinas_command,
    tipos_command,
    pendientes_command,
    correlativo_command,
    buscar_command,
    handle_document,
    handle_callback,
    handle_correction_text,
    doc_command,
    documentos_command,
    fecha_command,
    estado_command,
    oficina_command,
    resumen_command,
    paginacion_callback,
    memos_command,
    notas_command,
    oficios_command,
    informes_command,
    circulares_command,
    actas_command,
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def setup_application(polling: bool = True) -> Application:
    """Configurar y retornar la aplicación de Telegram."""
    
    if not get_settings_instance().TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurado")
        sys.exit(1)
    
    application = Application.builder().token(get_settings_instance().TELEGRAM_BOT_TOKEN).build()
    
    # Handlers de comandos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ayuda", ayuda_command))
    application.add_handler(CommandHandler("oficinas", oficinas_command))
    application.add_handler(CommandHandler("tipos", tipos_command))
    application.add_handler(CommandHandler("pendientes", pendientes_command))
    application.add_handler(CommandHandler("correlativo", correlativo_command))
    application.add_handler(CommandHandler("buscar", buscar_command))

    # Consultas de documentos (backend/Postgres, solo lectura)
    application.add_handler(CommandHandler("doc", doc_command))
    application.add_handler(CommandHandler("documentos", documentos_command))
    application.add_handler(CommandHandler("memos", memos_command))
    application.add_handler(CommandHandler("notas", notas_command))
    application.add_handler(CommandHandler("oficios", oficios_command))
    application.add_handler(CommandHandler("informes", informes_command))
    application.add_handler(CommandHandler("circulares", circulares_command))
    application.add_handler(CommandHandler("actas", actas_command))
    application.add_handler(CommandHandler("fecha", fecha_command))
    application.add_handler(CommandHandler("estado", estado_command))
    application.add_handler(CommandHandler("oficina", oficina_command))
    application.add_handler(CommandHandler("resumen", resumen_command))
    
    # Handler para documentos (fotos y archivos)
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL,
        handle_document
    ))
    
    # Handler para callbacks de botones inline
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Handler para correcciones de texto
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_correction_text
    ))
    
    # Inicializar bot_data para almacenamiento temporal
    application.bot_data = {}
    
    logger.info("Bot de Telegram configurado correctamente")
    return application


async def run_polling(app: Application):
    """Ejecutar bot en modo long polling."""
    logger.info("Iniciando bot en modo polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Mantener corriendo
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Deteniendo bot...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


async def run_webhook(app: Application):
    """Ejecutar bot en modo webhook (para producción)."""
    logger.info("Iniciando bot en modo webhook...")
    
    webhook_url = f"{get_settings_instance().BACKEND_URL}/webhook/telegram"
    
    await app.initialize()
    await app.start()
    
    await app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    
    logger.info(f"Webhook configurado en: {webhook_url}")
    
    # El servidor web (FastAPI) manejará las requests
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Deteniendo bot...")
    finally:
        await app.bot.delete_webhook()
        await app.stop()
        await app.shutdown()


async def main():
    parser = argparse.ArgumentParser(description="Office Secretary Document Agent - Telegram Bot")
    parser.add_argument("--polling", action="store_true", help="Usar long polling (desarrollo)")
    parser.add_argument("--webhook", action="store_true", help="Usar webhook (producción)")
    args = parser.parse_args()
    
    # Default a polling en desarrollo
    use_polling = args.polling or not args.webhook
    
    app = await setup_application(polling=use_polling)
    
    try:
        if use_polling:
            await run_polling(app)
        else:
            await run_webhook(app)
    except Exception as e:
        logger.error(f"Error fatal en bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())