"""El comando correlativo debe consultar la fuente principal, no Neo4j."""
import importlib.util
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

spec = importlib.util.spec_from_file_location("bot", "/app/__init__.py")
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)

from bot.handlers import telegram_handlers as handlers
from app.services.graphify_client import graphify_client


class CorrelativoTests(unittest.IsolatedAsyncioTestCase):
    async def test_correlativo_reads_active_documents_from_backend(self):
        update = MagicMock()
        update.message.message_thread_id = 3073
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.args = ["OTIC", "MEMO"]

        with (
            patch.object(handlers, "is_authorized", return_value=True),
            patch(
                "bot.core.backend_client.consultar_documentos",
                new=AsyncMock(return_value=[{
                    "correlativo": "OTIC-MEMO-2026-032",
                    "fecha_documento": "2026-07-07",
                }]),
            ) as consultar,
            patch.object(
                graphify_client, "get_last_correlativo",
                new=AsyncMock(return_value={"correlativo": "OTIC-TEST-2026-006"}),
            ) as graph_query,
        ):
            await handlers.correlativo_command(update, context)

        consultar.assert_awaited_once_with(
            oficina_origen="OTIC", tipo_documento="MEMO", limit=1,
        )
        graph_query.assert_not_called()
        response = update.message.reply_text.await_args.args[0]
        self.assertIn("OTIC-MEMO-2026-032", response)
        self.assertNotIn("OTIC-TEST-2026-006", response)


if __name__ == "__main__":
    unittest.main()
