"""Regresiones de autenticación: firma, expiración y autorización real."""
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from jose import jwt

import app.main as backend

SECRET = os.environ["SUPABASE_JWT_SECRET"]


def request(headers=None):
    return SimpleNamespace(headers=headers or {}, state=SimpleNamespace())


def token(email="persona@corpocentro.gob.ve", role="ADMIN", exp=None, secret=SECRET):
    return jwt.encode(
        {"sub": "user-id", "email": email, "role": "authenticated",
         "user_metadata": {"role": role}, "exp": exp or int(time.time()) + 3600},
        secret, algorithm="HS256",
    )


def persona(role="SECRETARIO", oficina="OTIC"):
    response = MagicMock(status_code=200)
    response.json.return_value = [{
        "id": "persona-id", "email": "persona@corpocentro.gob.ve",
        "oficina_sigla": oficina, "activa": True,
    }]
    return response


class AuthSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_forged_admin_token_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            await backend.get_current_user(request({
                "Authorization": f"Bearer {token(secret='secreto-falso')}"
            }))
        self.assertEqual(error.exception.status_code, 401)

    async def test_expired_token_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            await backend.get_current_user(request({
                "Authorization": f"Bearer {token(exp=int(time.time()) - 60)}"
            }))
        self.assertEqual(error.exception.status_code, 401)

    async def test_missing_token_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            await backend.get_current_user(request())
        self.assertEqual(error.exception.status_code, 401)

    async def test_role_comes_from_database_not_token_metadata(self):
        client = MagicMock()
        client.get = AsyncMock(return_value=persona())
        cursor = MagicMock()
        cursor.fetchone.return_value = ("SECRETARIO",)
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with (
            patch.object(backend, "supabase_http_client", client),
            patch.object(backend.psycopg, "connect", return_value=connection),
        ):
            user = await backend.get_current_user(request({
                "Authorization": f"Bearer {token(role='ADMIN')}"
            }))
        self.assertEqual(user.role, "SECRETARIO")
        self.assertEqual(user.oficina_sigla, "OTIC")
        self.assertFalse(user.is_service)

    async def test_service_key_is_not_admin(self):
        with patch.dict(os.environ, {"OSDA_BOT_SERVICE_KEY": "service-test-key"}):
            user = await backend.get_current_user(request({
                "X-OSDA-Service-Key": "service-test-key"
            }))
        self.assertEqual(user.role, "BOT")
        self.assertTrue(user.is_service)
        self.assertNotEqual(user.role, "ADMIN")

    async def test_service_cannot_use_admin_routes(self):
        with patch.dict(os.environ, {"OSDA_BOT_SERVICE_KEY": "service-test-key"}):
            with self.assertRaises(HTTPException) as error:
                await backend.require_admin(request({"X-OSDA-Service-Key": "service-test-key"}))
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
