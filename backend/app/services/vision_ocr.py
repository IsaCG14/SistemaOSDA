"""
Vision OCR Pipeline for Office Secretary Document Agent.
Handles document processing with Ollama Vision API and NVIDIA Cloud API.
"""
import base64
import json
import httpx
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Resultado estandarizado de OCR."""
    tipo_documento: str
    correlativo: str
    fecha_documento: Optional[str]
    fecha_recepcion: Optional[str]
    remitente: str
    destinatario: str
    asunto: str
    oficina_origen: str
    oficina_destino: str
    folios: Optional[int]
    anexos: list
    observaciones: Optional[str]
    confianza: float
    estado: str = "PENDIENTE"
    accion_sugerida: str = "REVISAR"


class BaseVisionProcessor(ABC):
    """Clase base abstracta para procesadores de visión."""
    
    def __init__(self, api_url: str, model: str, timeout: int = 120):
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
    
    def _encode_file(self, file_path: str) -> str:
        """Codifica archivo a base64."""
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _calculate_confidence(self, response_data: Dict[str, Any]) -> float:
        """Calcula confianza basada en la respuesta."""
        try:
            if "confianza" in response_data:
                return float(response_data["confianza"])
            # Si no hay campo confianza, estimar por completitud
            required_fields = ["tipo_documento", "correlativo", "fecha_documento", "remitente", "destinatario", "asunto"]
            filled = sum(1 for f in required_fields if response_data.get(f))
            return round(filled / len(required_fields), 2)
        except Exception:
            return 0.5
    
    def _determine_action(self, confianza: float) -> str:
        """Determina acción sugerida según confianza."""
        if confianza >= 0.85:
            return "APROBAR"
        elif confianza >= 0.60:
            return "REVISAR"
        else:
            return "RECHAZAR"
    
    async def _wait_before_retry(self, attempt: int, base_delay: float = 1.0):
        """Espera exponencial antes de reintentar."""
        import asyncio
        delay = base_delay * (2 ** attempt)
        await asyncio.sleep(delay)
    
    @abstractmethod
    async def process(self, file_path: str, mime_type: str) -> OCRResult:
        """Procesa un archivo y retorna resultado OCR."""
        pass
    
    def _parse_vision_response(self, text: str) -> Dict[str, Any]:
        """Parsea respuesta del modelo de visión."""
        try:
            # Buscar JSON en la respuesta
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
        except Exception as e:
            logger.warning("Failed to parse vision response as JSON", error=str(e))
        return {}


class VisionOCRProcessor(BaseVisionProcessor):
    """Procesador OCR usando Ollama Vision API."""
    
    def __init__(self, ollama_url: str, vision_model: str):
        super().__init__(ollama_url, vision_model)
        self.prompt_template = self._build_prompt()
    
    def _build_prompt(self) -> str:
        return """Analiza esta imagen de un documento oficial y extrae la información en formato JSON.
        
Devuelve SOLO un objeto JSON con estos campos exactos:
{
  "tipo_documento": "MEMO|NOTA|OFICIO|INFORME|RESOLUCION|OTRO",
  "correlativo": "string (ej: OTIC-MEMO-2026-001)",
  "fecha_documento": "YYYY-MM-DD o null",
  "fecha_recepcion": "YYYY-MM-DD o null",
  "remitente": "string",
  "destinatario": "string",
  "asunto": "string",
  "oficina_origen": "string (sigla)",
  "oficina_destino": "string (sigla)",
  "folios": number o null,
  "anexos": ["string"],
  "observaciones": "string o null",
  "confianza": 0.0-1.0
}

Reglas:
- Si no ves el campo, usa null o string vacío
- correlativo: busca patrón XXX-XXX-YYYY-NNN
- fechas: normaliza a YYYY-MM-DD
- oficina_origen/destino: usa siglas oficiales (OTIC, PR, SA, JUR, etc.)
- confianza: tu certeza en la extracción (0.0-1.0)
"""
    
    async def process(self, file_path: str, mime_type: str) -> OCRResult:
        """Procesa imagen con Ollama Vision."""
        import asyncio
        
        base64_image = self._encode_file(file_path)
        
        payload = {
            "model": self.model,
            "prompt": self.prompt_template,
            "images": [base64_image],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.api_url}/api/generate",
                        json=payload
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    parsed = self._parse_vision_response(data.get("response", ""))
                    
                    if not parsed:
                        logger.warning("Empty parsed result, retrying", attempt=attempt+1)
                        await self._wait_before_retry(attempt)
                        continue
                    
                    confianza = self._calculate_confidence(parsed)
                    accion = self._determine_action(confianza)
                    
                    return OCRResult(
                        tipo_documento=parsed.get("tipo_documento", "OTRO"),
                        correlativo=parsed.get("correlativo", ""),
                        fecha_documento=parsed.get("fecha_documento"),
                        fecha_recepcion=parsed.get("fecha_recepcion"),
                        remitente=parsed.get("remitente", ""),
                        destinatario=parsed.get("destinatario", ""),
                        asunto=parsed.get("asunto", ""),
                        oficina_origen=parsed.get("oficina_origen", ""),
                        oficina_destino=parsed.get("oficina_destino", ""),
                        folios=parsed.get("folios"),
                        anexos=parsed.get("anexos", []),
                        observaciones=parsed.get("observaciones"),
                        confianza=confianza,
                        accion_sugerida=accion
                    )
                    
            except httpx.TimeoutException:
                logger.warning("Ollama timeout", attempt=attempt+1)
            except httpx.HTTPStatusError as e:
                logger.error("Ollama HTTP error", status=e.response.status_code)
            except Exception as e:
                logger.error("Ollama processing error", error=str(e))
            
            if attempt < max_retries - 1:
                await self._wait_before_retry(attempt)
        
        # Fallback si todos los reintentos fallan
        return OCRResult(
            tipo_documento="OTRO",
            correlativo="",
            fecha_documento=None,
            fecha_recepcion=None,
            remitente="",
            destinatario="",
            asunto="",
            oficina_origen="",
            oficina_destino="",
            folios=None,
            anexos=[],
            observaciones="Error en OCR tras reintentos",
            confianza=0.0,
            accion_sugerida="RECHAZAR"
        )


class NVIDIAVisionProcessor(BaseVisionProcessor):
    """Procesador OCR usando NVIDIA Cloud API (Nemotron 3 Ultra / Gemma)."""
    
    def __init__(self, api_key: str, model: str = "google/gemma-4-31b-it"):
        # NVIDIA usa endpoint diferente
        super().__init__("https://integrate.api.nvidia.com/v1", model)
        self.api_key = api_key
        self.prompt_template = self._build_prompt()
    
    def _build_prompt(self) -> str:
        return """Analiza esta imagen de un documento oficial y extrae la información en formato JSON.
        
Devuelve SOLO un objeto JSON con estos campos exactos:
{
  "tipo_documento": "MEMO|NOTA|OFICIO|INFORME|RESOLUCION|OTRO",
  "correlativo": "string (ej: OTIC-MEMO-2026-001)",
  "fecha_documento": "YYYY-MM-DD o null",
  "fecha_recepcion": "YYYY-MM-DD o null",
  "remitente": "string",
  "destinatario": "string",
  "asunto": "string",
  "oficina_origen": "string (sigla)",
  "oficina_destino": "string (sigla)",
  "folios": number o null,
  "anexos": ["string"],
  "observaciones": "string o null",
  "confianza": 0.0-1.0
}

Reglas:
- Si no ves el campo, usa null o string vacío
- correlativo: busca patrón XXX-XXX-YYYY-NNN
- fechas: normaliza a YYYY-MM-DD
- oficina_origen/destino: usa siglas oficiales (OTIC, PR, SA, JUR, etc.)
- confianza: tu certeza en la extracción (0.0-1.0)
"""
    
    async def process(self, file_path: str, mime_type: str) -> OCRResult:
        """Procesa imagen con NVIDIA Vision API."""
        import asyncio
        
        base64_image = self._encode_file(file_path)
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt_template},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.1,
            "top_p": 0.9,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.api_url}/chat/completions",
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    content = data["choices"][0]["message"]["content"]
                    parsed = self._parse_vision_response(content)
                    
                    if not parsed:
                        logger.warning("Empty parsed result, retrying", attempt=attempt+1)
                        await self._wait_before_retry(attempt)
                        continue
                    
                    confianza = self._calculate_confidence(parsed)
                    accion = self._determine_action(confianza)
                    
                    return OCRResult(
                        tipo_documento=parsed.get("tipo_documento", "OTRO"),
                        correlativo=parsed.get("correlativo", ""),
                        fecha_documento=parsed.get("fecha_documento"),
                        fecha_recepcion=parsed.get("fecha_recepcion"),
                        remitente=parsed.get("remitente", ""),
                        destinatario=parsed.get("destinatario", ""),
                        asunto=parsed.get("asunto", ""),
                        oficina_origen=parsed.get("oficina_origen", ""),
                        oficina_destino=parsed.get("oficina_destino", ""),
                        folios=parsed.get("folios"),
                        anexos=parsed.get("anexos", []),
                        observaciones=parsed.get("observaciones"),
                        confianza=confianza,
                        accion_sugerida=accion
                    )
                    
            except httpx.TimeoutException:
                logger.warning("NVIDIA API timeout", attempt=attempt+1)
            except httpx.HTTPStatusError as e:
                logger.error("NVIDIA API HTTP error", status=e.response.status_code)
            except Exception as e:
                logger.error("NVIDIA processing error", error=str(e))
            
            if attempt < max_retries - 1:
                await self._wait_before_retry(attempt)
        
        # Fallback
        return OCRResult(
            tipo_documento="OTRO",
            correlativo="",
            fecha_documento=None,
            fecha_recepcion=None,
            remitente="",
            destinatario="",
            asunto="",
            oficina_origen="",
            oficina_destino="",
            folios=None,
            anexos=[],
            observaciones="Error en OCR tras reintentos",
            confianza=0.0,
            accion_sugerida="RECHAZAR"
        )


def get_vision_processor(provider: str, **kwargs) -> BaseVisionProcessor:
    """Factory para obtener procesador de visión según proveedor."""
    if provider == "nvidia":
        api_key = kwargs.get("api_key")
        if not api_key:
            raise ValueError("NVIDIA_API_KEY requerido para proveedor nvidia")
        model = kwargs.get("model", "google/gemma-4-31b-it")
        return NVIDIAVisionProcessor(api_key=api_key, model=model)
    else:
        # Default: Ollama
        ollama_url = kwargs.get("ollama_url", "http://ollama:11434")
        vision_model = kwargs.get("vision_model", "llava:latest")
        return VisionOCRProcessor(ollama_url=ollama_url, vision_model=vision_model)