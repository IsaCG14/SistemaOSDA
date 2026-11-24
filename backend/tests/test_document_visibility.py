"""Regresiones: documentos eliminados no deben volver a las consultas."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import app.main as backend
from app.main import delete_documento, list_documentos, ultimo_correlativo, update_documento


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        return None


class DocumentVisibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_excludes_soft_deleted_documents_from_results_and_count(self):
        client = MagicMock()
        client.get = AsyncMock(side_effect=[FakeResponse([{"count": 0}]), FakeResponse([])])

        await list_documentos(request=MagicMock(), user_office=None, client=client)

        self.assertEqual(client.get.await_count, 2)
        for call in client.get.await_args_list:
            self.assertIn(("eliminado_en", "is.null"), call.kwargs["params"])

    async def test_last_correlativo_uses_postgres_and_excludes_deleted(self):
        client = MagicMock()
        client.get = AsyncMock(return_value=FakeResponse([
            {"correlativo": "OTIC-MEMO-2026-032", "fecha_documento": "2026-07-07"}
        ]))

        result = await ultimo_correlativo(
            oficina="OTIC", tipo_documento="MEMO", client=client,
        )

        self.assertEqual(result["correlativo"], "OTIC-MEMO-2026-032")
        params = client.get.await_args.kwargs["params"]
        self.assertIn(("eliminado_en", "is.null"), params)
        self.assertIn(("oficina_origen_sigla", "eq.OTIC"), params)
        self.assertIn(("tipo_doc_codigo", "eq.MEMO"), params)

    async def test_delete_marks_eliminado_en_instead_of_archiving(self):
        client = MagicMock()
        client.get = AsyncMock(return_value=FakeResponse([{
            "estado": "RECIBIDO",
            "oficina_origen_sigla": "OTIC",
            "oficina_destino_sigla": "DG",
            "eliminado_en": None,
        }]))
        client.patch = AsyncMock(return_value=FakeResponse([{"id": "doc-id"}]))

        with patch.object(backend, "graphify_client", None):
            result = await delete_documento(
                "doc-id", request=MagicMock(), user_info=(None, "ADMIN"), client=client,
            )

        self.assertEqual(result["message"], "Documento eliminado")
        data = client.patch.await_args.kwargs["json"]
        self.assertIsNotNone(data["eliminado_en"])
        self.assertNotIn("estado", data)
        client.delete.assert_not_called()

    async def test_update_does_not_send_telegram_user_id_to_postgrest(self):
        doc = backend.DocumentoCreate(
            correlativo="OTIC-PRUEBA-EDICION",
            tipo_doc_codigo="OFICIO",
            oficina_origen_sigla="OTIC",
            oficina_destino_sigla="DG",
            fecha_documento="2026-11-20",
            asunto="Asunto corregido",
            telegram_user_id=1630681340,
        )
        updated = doc.model_dump(exclude={"telegram_user_id"})
        updated.update({"id": "doc-id", "creado_en": "2026-11-20T12:00:00"})
        client = MagicMock()
        client.get = AsyncMock(return_value=FakeResponse([{
            "oficina_origen_sigla": "OTIC",
            "oficina_destino_sigla": "DG",
        }]))
        client.patch = AsyncMock(return_value=FakeResponse([updated]))

        await update_documento(
            "doc-id", doc=doc, request=MagicMock(),
            user_info=(None, "ADMIN"), client=client,
        )

        payload = client.patch.await_args.kwargs["json"]
        self.assertNotIn("telegram_user_id", payload)
        self.assertEqual(payload["asunto"], "Asunto corregido")


if __name__ == "__main__":
    unittest.main()
