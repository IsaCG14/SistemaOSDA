"""
Graphify Client for Office Secretary Document Agent.
Connects to the Graphify API service for graph-based document queries.
"""
import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class GraphifyClient:
    """Cliente para interactuar con Graphify API."""
    
    def __init__(self):
        self.base_url = settings.GRAPHIFY_URL
        self.index_name = settings.GRAPHIFY_INDEX_NAME
        self.timeout = 30.0
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> bool:
        """Verificar si Graphify está disponible."""
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Graphify health check failed: {e}")
            return False
    
    # ─────────────────────────────────────────────────────────────────
    # DOCUMENT INDEXING
    # ─────────────────────────────────────────────────────────────────
    
    async def index_document(self, document_data: Dict[str, Any]) -> bool:
        """Indexar un documento confirmado en Graphify."""
        try:
            # Preparar datos para Graphify
            payload = self._prepare_document_payload(document_data)
            
            resp = await self.client.post(
                f"{self.base_url}/documents",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code in (200, 201):
                logger.info(f"Documento indexado en Graphify: {document_data.get('correlativo')}")
                return True
            else:
                logger.error(f"Error indexando en Graphify: {resp.status_code} - {resp.text}")
                return False
                
        except Exception as e:
            logger.error(f"Excepción indexando documento: {e}")
            return False
    
    async def bulk_index_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        """Indexar múltiples documentos en lote."""
        results = {"success": 0, "failed": 0}
        
        for doc in documents:
            try:
                success = await self.index_document(doc)
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception:
                results["failed"] += 1
        
        return results
    
    async def update_document(self, document_id: str, document_data: Dict[str, Any]) -> bool:
        """Actualizar documento en Graphify."""
        try:
            payload = self._prepare_document_payload(document_data)
            payload["id"] = document_id
            
            resp = await self.client.put(
                f"{self.base_url}/documents/{document_id}",
                json=payload
            )
            
            return resp.status_code == 200
            
        except Exception as e:
            logger.error(f"Error actualizando documento en Graphify: {e}")
            return False
    
    async def delete_document(self, document_id: str) -> bool:
        """Eliminar documento de Graphify (soft delete - marcar como archivado)."""
        try:
            resp = await self.client.delete(f"{self.base_url}/documents/{document_id}")
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Error eliminando documento de Graphify: {e}")
            return False
    
    def _prepare_document_payload(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Preparar payload para Graphify."""
        return {
            "id": doc.get("id"),
            "correlativo": doc.get("correlativo"),
            "tipo_documento": doc.get("tipo_doc_codigo") or doc.get("tipo_documento"),
            "oficina_origen": doc.get("oficina_origen_sigla") or doc.get("oficina_origen"),
            "oficina_destino": doc.get("oficina_destino_sigla") or doc.get("oficina_destino"),
            "fecha_documento": str(doc.get("fecha_documento")) if doc.get("fecha_documento") else None,
            "fecha_recepcion": str(doc.get("fecha_recepcion")) if doc.get("fecha_recepcion") else None,
            "remitente": doc.get("remitente") or (doc.get("remitente_id") and str(doc.get("remitente_id"))),
            "destinatario": doc.get("destinatario") or (doc.get("destinatario_id") and str(doc.get("destinatario_id"))),
            "asunto": doc.get("asunto"),
            "folios": doc.get("folios"),
            "anexos": doc.get("anexos", []),
            "estado": doc.get("estado"),
            "prioridad": doc.get("prioridad"),
            "observaciones": doc.get("observaciones"),
            "confianza_ocr": doc.get("confianza_ocr"),
            "created_at": doc.get("creado_en") or doc.get("created_at"),
            "updated_at": doc.get("actualizado_en") or doc.get("updated_at"),
        }
    
    # ─────────────────────────────────────────────────────────────────
    # GRAPH QUERIES
    # ─────────────────────────────────────────────────────────────────
    
    async def trace_document(self, correlativo: str) -> Optional[Dict[str, Any]]:
        """Obtener trazabilidad completa de un documento."""
        try:
            resp = await self.client.get(f"{self.base_url}/trace/{correlativo}")
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return None
            else:
                logger.error(f"Error trace: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error en trace_document: {e}")
            return None
    
    async def get_pending_documents(self, days_limit: int = 5) -> List[Dict[str, Any]]:
        """Obtener documentos pendientes de respuesta."""
        try:
            resp = await self.client.get(
                f"{self.base_url}/consultas/pendientes",
                params={"dias_limite": days_limit}
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Error getting pendientes: {e}")
            return []
    
    async def get_last_correlativo(self, oficina: str, tipo_documento: str) -> Optional[Dict[str, Any]]:
        """Obtener último correlativo para una oficina y tipo."""
        try:
            resp = await self.client.get(
                f"{self.base_url}/consultas/ultimo-correlativo",
                params={"oficina": oficina, "tipo_documento": tipo_documento}
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Error getting ultimo correlativo: {e}")
            return None
    
    async def get_documents_by_office(
        self, 
        oficina: str, 
        mes: Optional[int] = None, 
        año: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Obtener documentos de una oficina en un período."""
        try:
            params = {"oficina": oficina}
            if mes and año:
                params["mes"] = mes
                params["año"] = año
            
            resp = await self.client.get(
                f"{self.base_url}/consultas/por-oficina",
                params=params
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Error getting documents by office: {e}")
            return []
    
    async def search_documents(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Búsqueda en lenguaje natural (si Graphify lo soporta)."""
        try:
            resp = await self.client.post(
                f"{self.base_url}/query",
                json={"query": query, "limit": limit}
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Error en search_documents: {e}")
            return []
    
    async def custom_cypher_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Ejecutar query Cypher personalizada (solo lectura)."""
        try:
            resp = await self.client.post(
                f"{self.base_url}/query",
                json={"query": query, "params": params or {}}
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"Error en custom_cypher_query: {e}")
            return []


# Instancia global
graphify_client = GraphifyClient()