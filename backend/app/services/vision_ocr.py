"""
Vision OCR Pipeline for Office Secretary Document Agent.
Handles document processing with Ollama Vision API and NVIDIA Cloud API.
"""
import base64
import json
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class VisionOCRProcessor:
    """Procesador de OCR usando Ollama Vision API."""

    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.vision_model = settings.VISION_MODEL
        self.timeout = 180  # 3 minutos para CPU

        # Umbrales de confianza
        self.confidence_auto_approve = settings.CONFIDENCE_AUTO_APPROVE
        self.confidence_review = settings.CONFIDENCE_REVIEW
        self.confidence_reject = settings.CONFIDENCE_REJECT

    async def extract_document_data(
        self,
        file_path: str,
        mime_type: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Extraer datos estructurados de un documento (imagen/PDF).

        Returns:
            Dict con: success, data, confidence, error, raw_response
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Procesando OCR intento {attempt + 1}/{max_retries}: {file_path}")

                # Leer y codificar archivo
                b64_data = await self._encode_file(file_path)

                # Construir prompt
                prompt = self._build_extraction_prompt()

                # Llamar a Ollama
                result = await self._call_ollama_vision(b64_data, prompt)

                # Parsear respuesta JSON
                parsed = self._parse_vision_response(result["response"])

                # Calcular confianza
                confidence = self._calculate_confidence(parsed)
                parsed["confidence"] = confidence

                # Determinar acción recomendada
                action = self._determine_action(confidence)
                parsed["recommended_action"] = action

                logger.info(f"OCR completado - Confianza: {confidence:.2%}, Accion: {action}")

                return {
                    "success": True,
                    "data": parsed,
                    "confidence": confidence,
                    "recommended_action": action,
                    "raw_response": result["response"],
                    "attempts": attempt + 1,
                }

            except Exception as e:
                logger.warning(f"Intento {attempt + 1} fallo: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Todos los intentos fallaron para {file_path}")
                    return {
                        "success": False,
                        "data": None,
                        "confidence": 0.0,
                        "recommended_action": "REJECT",
                        "error": str(e),
                        "attempts": attempt + 1,
                    }

                # Esperar antes de reintentar
                await self._wait_before_retry(attempt)

        return {
            "success": False,
            "data": None,
            "confidence": 0.0,
            "recommended_action": "REJECT",
            "error": "Max retries exceeded",
        }

    async def _encode_file(self, file_path: str) -> str:
        """Leer archivo y convertir a base64."""
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode("utf-8")

    def _build_extraction_prompt(self) -> str:
        """Construir prompt para extraccion estructurada."""
        return """
Extrae la siguiente informacion de este documento administrativo en formato JSON estricto:
{
    "correlativo": "numero de correlativo (ej: OTIC-MEMO-2026-0001)",
    "fecha_documento": "YYYY-MM-DD",
    "fecha_recepcion": "YYYY-MM-DD o null",
    "remitente": "nombre y cargo de quien firma/envia",
    "destinatario": "nombre y cargo de quien recibe",
    "oficina_origen": "sigla de la oficina que envia (ej: OTIC, OGA, DP, DG, OGH, OPP, UAI, OAC)",
    "oficina_destino": "sigla de la oficina que recibe",
    "tipo_documento": "MEMO, OFICIO, CIRCULAR, INFORME, NOTA, ACTA, RESOLUCION, SOLICITUD, RECIBO, OTRO",
    "asunto": "asunto o referencia del documento",
    "folios": "numero de paginas/folios o null",
    "anexos": ["lista de anexos mencionados"] o [],
    "observaciones": "cualquier observacion adicional, sellos, firmas, plazos, fechas limite"
}

REGLAS IMPORTANTES:
1. Si un campo no es legible o no existe, pon null (no omitas el campo)
2. Para fechas, usa formato ISO YYYY-MM-DD
3. Para oficinas, usa solo las siglas conocidas: OTIC, OGA, OGH, OPP, DP, DG, UAI, OAC, JUR, COM
4. El correlativo debe incluir prefijo de oficina, tipo, ano y secuencial
5. Responde SOLO con el JSON valido, sin texto adicional
6. Si hay sellos de "RECIBIDO" con fecha, usalo para fecha_recepcion
7. Si hay multiples destinatarios, pon el principal en destinatario y los otros en observaciones
"""

    async def _call_ollama_vision(self, b64_image: str, prompt: str) -> Dict[str, Any]:
        """Llamar a Ollama API para vision."""
        # Usar trust_env=False para ignorar proxy env vars (HTTP_PROXY, HTTPS_PROXY)
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [b64_image],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1024,
                        "top_p": 0.9,
                    }
                }
            )

            if response.status_code != 200:
                raise Exception(f"Ollama HTTP {response.status_code}: {response.text}")

            return response.json()

    def _parse_vision_response(self, response_text: str) -> Dict[str, Any]:
        """Parsear respuesta de Ollama para extraer JSON."""
        # Remover markdown code fences si existen (```json ... ```)
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.rfind("```")
            if start >= 7 and end > start:
                response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.rfind("```")
            if start >= 3 and end > start:
                response_text = response_text[start:end].strip()
        
        # Buscar JSON en la respuesta
        start = response_text.find("{")
        end = response_text.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = response_text[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Error parseando JSON de Vision: {e}")
                logger.debug(f"Respuesta raw: {response_text[:500]}")

        # Fallback: intentar parsear toda la respuesta
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Si todo falla, retornar estructura vacia
        return {
            "correlativo": None,
            "fecha_documento": None,
            "fecha_recepcion": None,
            "remitente": None,
            "destinatario": None,
            "oficina_origen": None,
            "oficina_destino": None,
            "tipo_documento": None,
            "asunto": None,
            "folios": None,
            "anexos": [],
            "observaciones": "No se pudo parsear respuesta de Vision API",
        }

    def _calculate_confidence(self, parsed_data: Dict[str, Any]) -> float:
        """Calcular confianza global basada en campos completados."""
        if not parsed_data:
            return 0.0

        # Campos criticos (peso alto)
        critical_fields = ["correlativo", "fecha_documento", "oficina_origen", "oficina_destino"]
        # Campos importantes (peso medio)
        important_fields = ["tipo_documento", "remitente", "destinatario", "fecha_recepcion"]
        # Campos opcionales (peso bajo)
        optional_fields = ["asunto", "folios", "anexos", "observaciones"]

        weights = {
            "critical": 0.5,
            "important": 0.3,
            "optional": 0.2,
        }

        scores = {}
        for category, fields, weight in [
            ("critical", critical_fields, weights["critical"]),
            ("important", important_fields, weights["important"]),
            ("optional", optional_fields, weights["optional"]),
        ]:
            filled = sum(1 for f in fields if parsed_data.get(f) not in [None, "", []])
            total = len(fields)
            scores[category] = (filled / total) * weight if total > 0 else 0

        return sum(scores.values())

    def _determine_action(self, confidence: float) -> str:
        """Determinar accion recomendada basada en confianza."""
        if confidence >= self.confidence_auto_approve:
            return "AUTO_APPROVE"
        elif confidence >= self.confidence_review:
            return "REVIEW"
        else:
            return "REJECT"

    async def _wait_before_retry(self, attempt: int):
        """Esperar antes de reintentar con backoff exponencial."""
        import asyncio
        wait_times = [2, 5, 10]  # segundos
        wait = wait_times[min(attempt, len(wait_times) - 1)]
        await asyncio.sleep(wait)


class NVIDIAVisionProcessor:
    """Procesador de OCR usando NVIDIA Cloud API (Llama 3.2 90B Vision)."""

    def __init__(self):
        self.api_key = settings.NVIDIA_API_KEY
        self.base_url = "https://integrate.api.nvidia.com/v1"
        self.model = "meta/llama-3.2-90b-vision-instruct"
        self.timeout = 180  # Aumentado a 180s para red lenta

        # Umbrales de confianza
        self.confidence_auto_approve = settings.CONFIDENCE_AUTO_APPROVE
        self.confidence_review = settings.CONFIDENCE_REVIEW
        self.confidence_reject = settings.CONFIDENCE_REJECT

    async def extract_document_data(
        self,
        file_path: str,
        mime_type: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Extraer datos estructurados de un documento (imagen/PDF) usando NVIDIA Cloud."""
        for attempt in range(max_retries):
            try:
                logger.info(f"Procesando OCR NVIDIA intento {attempt + 1}/{max_retries}: {file_path}")

                # Leer y codificar archivo
                b64_data = await self._encode_file(file_path)
                logger.info(f"File encoded to base64, length: {len(b64_data)}")

                # Construir prompt
                prompt = self._build_extraction_prompt()

                # Llamar a NVIDIA API
                result = await self._call_nvidia_vision(b64_data, prompt)

                # Parsear respuesta JSON
                parsed = self._parse_vision_response(result)
                logger.info(f"Parsed vision response: {parsed}")

                # Calcular confianza
                confidence = self._calculate_confidence(parsed)
                parsed["confidence"] = confidence

                # Determinar accion recomendada
                action = self._determine_action(confidence)
                parsed["recommended_action"] = action

                logger.info(f"OCR NVIDIA completado - Confianza: {confidence:.2%}, Accion: {action}")

                return {
                    "success": True,
                    "data": parsed,
                    "confidence": confidence,
                    "recommended_action": action,
                    "raw_response": result,
                    "attempts": attempt + 1,
                }

            except Exception as e:
                logger.warning(f"Intento NVIDIA {attempt + 1} fallo: {e}", exc_info=True)
                if attempt == max_retries - 1:
                    logger.error(f"Todos los intentos NVIDIA fallaron para {file_path}")
                    return {
                        "success": False,
                        "data": None,
                        "confidence": 0.0,
                        "recommended_action": "REJECT",
                        "error": str(e),
                        "attempts": attempt + 1,
                    }

                # Esperar antes de reintentar
                await self._wait_before_retry(attempt)

        return {
            "success": False,
            "data": None,
            "confidence": 0.0,
            "recommended_action": "REJECT",
            "error": "Max retries exceeded",
        }

    async def _encode_file(self, file_path: str) -> str:
        """Leer archivo y convertir a base64."""
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode("utf-8")

    def _build_extraction_prompt(self) -> str:
        """Construir prompt para extraccion estructurada."""
        return """
Extrae la siguiente informacion de este documento administrativo en formato JSON estricto:
{
    "correlativo": "numero de correlativo (ej: OTIC-MEMO-2026-0001)",
    "fecha_documento": "YYYY-MM-DD",
    "fecha_recepcion": "YYYY-MM-DD o null",
    "remitente": "nombre y cargo de quien firma/envia",
    "destinatario": "nombre y cargo de quien recibe",
    "oficina_origen": "sigla de la oficina que envia (ej: OTIC, OGA, DP, DG, OGH, OPP, UAI, OAC)",
    "oficina_destino": "sigla de la oficina que recibe",
    "tipo_documento": "MEMO, OFICIO, CIRCULAR, INFORME, NOTA, ACTA, RESOLUCION, SOLICITUD, RECIBO, OTRO",
    "asunto": "asunto o referencia del documento",
    "folios": "numero de paginas/folios o null",
    "anexos": ["lista de anexos mencionados"] o [],
    "observaciones": "cualquier observacion adicional, sellos, firmas, plazos, fechas limite"
}

REGLAS IMPORTANTES:
1. Si un campo no es legible o no existe, pon null (no omitas el campo)
2. Para fechas, usa formato ISO YYYY-MM-DD
3. Para oficinas, usa solo las siglas conocidas: OTIC, OGA, OGH, OPP, DP, DG, UAI, OAC, JUR, COM
4. El correlativo debe incluir prefijo de oficina, tipo, ano y secuencial
5. Responde SOLO con el JSON valido, sin texto adicional
6. Si hay sellos de "RECIBIDO" con fecha, usalo para fecha_recepcion
7. Si hay multiples destinatarios, pon el principal en destinatario y los otros en observaciones
"""

    async def _call_nvidia_vision(self, b64_image: str, prompt: str) -> Dict[str, Any]:
        """Llamar a NVIDIA Cloud API para vision."""
        logger.info(f"Calling NVIDIA Vision API: model={self.model}, timeout={self.timeout}")
        # Configurar timeouts más granulares
        timeout = httpx.Timeout(connect=30.0, read=self.timeout, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                        ]
                    }],
                    "max_tokens": 2048,
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"NVIDIA API error: status={response.status_code}, detail={error_detail}")
                raise Exception(f"NVIDIA API {response.status_code}: {error_detail}")

            logger.info(f"NVIDIA API success: status={response.status_code}")
            return response.json()

    def _parse_vision_response(self, response_text: str) -> Dict[str, Any]:
        """Parsear respuesta de NVIDIA para extraer JSON."""
        # NVIDIA devuelve en choices[0].message.content
        try:
            # Si ya es dict, extraer content
            if isinstance(response_text, dict):
                content = response_text.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                # Parsear JSON de respuesta HTTP
                resp_json = json.loads(response_text)
                content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        except (json.JSONDecodeError, KeyError, IndexError):
            content = str(response_text)

        logger.debug(f"NVIDIA content raw: {content[:500]}")

        # Remover prefijo "**Answer:**" si existe
        if content.startswith("**Answer:**"):
            content = content[len("**Answer:**"):].strip()

        logger.debug(f"NVIDIA content after removing Answer prefix: {content[:500]}")

        # Buscar JSON en el content - buscar el primer { que no esté dentro de **Answer:**
        # Buscar desde el final hacia atrás para encontrar el último JSON completo
        start = content.find("{")
        end = content.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = content[start:end]
            # Fix escaped quotes in the JSON string (NVIDIA returns escaped quotes)
            json_str_fixed = json_str.replace('\\"', '"')
            try:
                return json.loads(json_str_fixed)
            except json.JSONDecodeError as e:
                logger.warning(f"Error parseando JSON de NVIDIA Vision: {e}")
                logger.debug(f"Respuesta raw: {content[:500]}")

        # Fallback: intentar parsear todo el content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Si todo falla, retornar estructura vacia
        return {
            "correlativo": None,
            "fecha_documento": None,
            "fecha_recepcion": None,
            "remitente": None,
            "destinatario": None,
            "oficina_origen": None,
            "oficina_destino": None,
            "tipo_documento": None,
            "asunto": None,
            "folios": None,
            "anexos": [],
            "observaciones": "No se pudo parsear respuesta de NVIDIA Vision API",
        }

    # Reutilizar metodos de calculo de confianza y accion del procesador base
    def _calculate_confidence(self, parsed_data: Dict[str, Any]) -> float:
        """Calcular confianza global basada en campos completados."""
        if not parsed_data:
            return 0.0

        critical_fields = ["correlativo", "fecha_documento", "oficina_origen", "oficina_destino"]
        important_fields = ["tipo_documento", "remitente", "destinatario", "fecha_recepcion"]
        optional_fields = ["asunto", "folios", "anexos", "observaciones"]

        weights = {
            "critical": 0.5,
            "important": 0.3,
            "optional": 0.2,
        }

        scores = {}
        for category, fields, weight in [
            ("critical", critical_fields, weights["critical"]),
            ("important", important_fields, weights["important"]),
            ("optional", optional_fields, weights["optional"]),
        ]:
            filled = sum(1 for f in fields if parsed_data.get(f) not in [None, "", []])
            total = len(fields)
            scores[category] = (filled / total) * weight if total > 0 else 0

        return sum(scores.values())

    def _determine_action(self, confidence: float) -> str:
        """Determinar accion recomendada basada en confianza."""
        if confidence >= self.confidence_auto_approve:
            return "AUTO_APPROVE"
        elif confidence >= self.confidence_review:
            return "REVIEW"
        else:
            return "REJECT"

    async def _wait_before_retry(self, attempt: int):
        """Esperar antes de reintentar con backoff exponencial."""
        import asyncio
        wait_times = [2, 5, 10]  # segundos
        wait = wait_times[min(attempt, len(wait_times) - 1)]
        await asyncio.sleep(wait)


# Factory para obtener el procesador segun configuracion
def get_vision_processor():
    """Factory para obtener el procesador de vision segun VISION_PROVIDER."""
    if settings.VISION_PROVIDER == "nvidia":
        return NVIDIAVisionProcessor()
    return VisionOCRProcessor()


# Instancia global (usa factory)
vision_processor = get_vision_processor()


async def process_document_vision(file_path: str, mime_type: str) -> Dict[str, Any]:
    """Funcion de conveniencia para procesar un documento."""
    return await vision_processor.extract_document_data(file_path, mime_type)