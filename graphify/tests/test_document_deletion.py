"""La réplica debe poder eliminar nodos huérfanos de documentos."""
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from main import delete_documento


class FakeSession:
    def __init__(self, deleted):
        self.deleted = deleted
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def run(self, query, **params):
        self.calls.append((query, params))
        result = MagicMock()
        result.single.return_value = {"deleted": self.deleted}
        return result


class FakeDriver:
    def __init__(self, deleted):
        self.fake_session = FakeSession(deleted)

    def session(self):
        return self.fake_session


class GraphifyDeleteTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_detaches_and_deletes_existing_document(self):
        driver = FakeDriver(deleted=1)
        result = await delete_documento("orphan-id", drv=driver)
        self.assertEqual(result["id"], "orphan-id")
        query, params = driver.fake_session.calls[0]
        self.assertIn("DETACH DELETE", query)
        self.assertEqual(params["id"], "orphan-id")

    async def test_delete_returns_404_for_missing_document(self):
        with self.assertRaises(HTTPException) as error:
            await delete_documento("missing-id", drv=FakeDriver(deleted=0))
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
