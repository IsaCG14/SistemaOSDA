"""
Application configuration using Pydantic Settings.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:changeme@localhost:5432/postgres",
        description="PostgreSQL connection URL"
    )
    DB_ECHO: bool = False
    
    # Supabase
    SUPABASE_URL: str = "http://supabase-kong:8000"
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    
    # Graphify
    GRAPHIFY_URL: str = "http://graphify:8080"
    GRAPHIFY_INDEX_NAME: str = "osda_docs"
    
    # Ollama
    OLLAMA_URL: str = "http://172.18.0.11:11434"
    VISION_MODEL: str = "llava:latest"
    VISION_PROVIDER: str = "ollama"
    NVIDIA_API_KEY: str = ""
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ALLOWED_CHAT_IDS: str = ""
    
    # App
    APP_SECRET_KEY: str = "changeme"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_MIME_TYPES: str = "image/jpeg,image/png,application/pdf"
    
    # Vision OCR thresholds
    CONFIDENCE_AUTO_APPROVE: float = 0.85
    CONFIDENCE_REVIEW: float = 0.50
    CONFIDENCE_REJECT: float = 0.30
    
    # Document states
    DOCUMENT_STATES: List[str] = [
        "RECIBIDO", "EN_TRAMITE", "RESPONDIDO", "ARCHIVADO", 
        "DERIVADO", "RECHAZADO", "EXTRAVIADO"
    ]
    
    # Document types
    DOCUMENT_TYPES: List[str] = [
        "MEMO", "OFICIO", "CIRCULAR", "INFORME", "NOTA", 
        "ACTA", "RESOLUCION", "SOLICITUD", "RECIBO", "OTRO"
    ]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()