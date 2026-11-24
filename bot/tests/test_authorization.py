"""Autorización de consultas en el grupo principal y su topic documental."""
import importlib.util
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("bot", "/app/__init__.py")
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)

from bot.handlers import telegram_handlers as handlers


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            TELEGRAM_ALLOWED_CHAT_IDS="-1001818577830",
            TELEGRAM_DOCUMENT_TOPIC_ID="3073",
        )

    def test_main_chat_of_allowed_group_is_accepted(self):
        with patch.object(handlers, "get_settings_instance", return_value=self.settings):
            self.assertTrue(handlers.is_authorized(-1001818577830, 1630681340, None))

    def test_document_topic_remains_accepted(self):
        with patch.object(handlers, "get_settings_instance", return_value=self.settings):
            self.assertTrue(handlers.is_authorized(-1001818577830, 1630681340, 3073))

    def test_other_chat_is_rejected(self):
        with patch.object(handlers, "get_settings_instance", return_value=self.settings):
            self.assertFalse(handlers.is_authorized(-1009999999999, 1630681340, None))

    def test_other_topic_is_rejected(self):
        with patch.object(handlers, "get_settings_instance", return_value=self.settings):
            self.assertFalse(handlers.is_authorized(-1001818577830, 1630681340, 9999))


if __name__ == "__main__":
    unittest.main()
