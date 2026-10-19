#!/usr/bin/env python3
"""
ETL script to migrate historical .md documents from a source directory
to the Office Secretary Document Agent database.

Usage:
    python scripts/migrate_historical_docs.py [--dry-run] [--source-dir PATH]
"""

import os
import re
import uuid
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List
import json

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.db.base import SessionLocal, engine, Base
from app.models import (
    Documento, Oficina, Persona, TipoDocumento, CorrelativoRegla,
    DocumentState, Priority
)
from app.core.config import settings


# Patrones para extraer información de los documentos markdown
CORRELATIVO_PATTERNS = [
    r'(?:Correlativo|N[úu]mero|Ref\.?|Referencia)[:\s]*([A-Z]{2,5}[-\w\d/]+)',
    r'^#\s*([A-Z]{2,5}[-\w\d/]+)',
    r'([A-Z]{2,5}-\d{4}-\d+)',
    r'([A-Z]{2,5}-\d{4}-\d{2}/\d{2})',
    r'([A-Z]{2,5}-\d{4}-\d{2,})',
]

FECHA_PATTERNS = [
    r'(?:Fecha|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
]

OFICINAS_CONOCIDAS = {
    'OTIC': 'Oficina de Tecnología de Información y Comunicación',
    'OGA': 'Oficina de Gestión Administrativa',
    'OGH': 'Oficina de Gestión Humana',
    'OPP': 'Oficina de Planificación y Presupuesto',
    'DP': 'Dirección de Planificación',
    'DG': 'Dirección General',
    'UAI': 'Unidad de Auditoría Interna',
    'OAC': 'Oficina de Administración y Contabilidad',
    'JUR': 'Asesoría Jurídica',
    'COM': 'Oficina de Comunicaciones',
}

TIPOS_DOC_MAP = {
    'memo': 'MEMO',
    'memorand': 'MEMO',
    'oficio': 'OFICIO',
    'circular': 'CIRCULAR',
    'informe': 'INFORME',
    'nota': 'NOTA',
    'entrega': 'NOTA',
    'acta': 'ACTA',
    'resolucion': 'RESOLUCION',
    'resolución': 'RESOLUCION',
    'solicitud': 'SOLICITUD',
    'recibo': 'RECIBO',
}


def extract_correlativo(text: str) -> Optional[str]:
    """Extraer correlativo del texto."""
    for pattern in CORRELATIVO_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            # Tomar el primero que parezca válido
            for m in matches:
                if re.search(r'[A-Z]{2,5}[-\d]', m):
                    return m.strip()
    return None


def extract_fecha(text: str, campo: str = 'fecha') -> Optional[date]:
    """Extraer fecha del texto."""
    for pattern in FECHA_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            for m in matches:
                # Intentar parsear diferentes formatos
                for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']:
                    try:
                        return datetime.strptime(m, fmt).date()
                    except ValueError:
                        continue
    return None


def extract_oficina_origen(text: str) -> Optional[str]:
    """Detectar oficina de origen desde el texto."""
    text_upper = text.upper()
    for sigla in OFICINAS_CONOCIDAS:
        if sigla in text_upper:
            return sigla
    return None


def extract_tipo_documento(text: str, filename: str) -> str:
    """Detectar tipo de documento."""
    text_lower = text.lower()
    filename_lower = filename.lower()
    
    for keyword, tipo in TIPOS_DOC_MAP.items():
        if keyword in text_lower or keyword in filename_lower:
            return tipo
    
    return 'OTRO'


def extract_remitente_destinatario(text: str) -> tuple:
    """Extraer remitente y destinatario básicos."""
    # Patrones simples
    remitente = None
    destinatario = None
    
    patterns_remitente = [
        r'(?:De|From|Remitente|Firma)[:\s]*([^\n]+)',
        r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s*(?:Director|Jefe|Analista|Coordinador)',
    ]
    
    patterns_destinatario = [
        r'(?:Para|To|Destinatario|CC)[:\s]*([^\n]+)',
    ]
    
    for pattern in patterns_remitente:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            remitente = match.group(1).strip()
            break
    
    for pattern in patterns_destinatario:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            destinatario = match.group(1).strip()
            break
    
    return remitente, destinatario


def extract_asunto(text: str) -> Optional[str]:
    """Extraer asunto del documento."""
    patterns = [
        r'(?:Asunto|Subject|Referencia|Ref)[:\s]*([^\n]+)',
        r'^#\s*[A-Z]{2,5}[-\w\d/]+\s*(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()[:500]
    
    # Fallback: primera línea no vacía después de headers
    lines = text.split('\n')
    for line in lines[1:10]:
        line = line.strip()
        if line and not line.startswith('#') and len(line) > 10:
            return line[:500]
    
    return None


def parse_markdown_file(filepath: Path) -> Dict[str, Any]:
    """Parsear un archivo .md y extraer metadatos."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extraer metadatos
    correlativo = extract_correlativo(content)
    fecha_doc = extract_fecha(content, 'fecha')
    fecha_rec = extract_fecha(content, 'recepcion') or fecha_doc
    oficina_origen = extract_oficina_origen(content)
    tipo_doc = extract_tipo_documento(content, filepath.name)
    remitente, destinatario = extract_remitente_destinatario(content)
    asunto = extract_asunto(content)
    
    # Si no hay correlativo, generar uno basado en filename
    if not correlativo:
        stem = filepath.stem
        # Limpiar nombre
        correlativo = re.sub(r'[^A-Z0-9\-/]', '', stem.upper())
        if not correlativo:
            correlativo = f"AUTO-{filepath.stem[:20].upper()}"
    
    return {
        'correlativo': correlativo,
        'tipo_doc_codigo': tipo_doc,
        'oficina_origen_sigla': oficina_origen or 'OTIC',
        'oficina_destino_sigla': 'OTIC',  # Default
        'fecha_documento': fecha_doc or date.today(),
        'fecha_recepcion': fecha_rec or date.today(),
        'remitente': remitente,
        'destinatario': destinatario,
        'asunto': asunto or f"Documento migrado: {filepath.name}",
        'folios': None,
        'anexos': [],
        'estado': 'ARCHIVADO',  # Históricos van directo a archivado
        'prioridad': 'NORMAL',
        'observaciones': f"Migrado desde archivo histórico: {filepath.name}",
        'confianza_ocr': 0.7,  # Baja confianza por ser migración
        'raw_content': content[:5000],  # Guardar preview
    }


def migrate_historical_docs(source_dir: Path, dry_run: bool = False) -> Dict[str, int]:
    """Migrar documentos históricos .md a la base de datos."""
    
    if not source_dir.exists():
        print(f"❌ Directorio no existe: {source_dir}")
        return {'processed': 0, 'inserted': 0, 'errors': 0}
    
    md_files = list(source_dir.rglob('*.md'))
    print(f"📁 Encontrados {len(md_files)} archivos .md en {source_dir}")
    
    stats = {'processed': 0, 'inserted': 0, 'skipped': 0, 'errors': 0}
    
    db = SessionLocal()
    try:
        # Asegurar que existan las oficinas y tipos básicos
        ensure_base_data(db)
        
        for md_file in md_files:
            stats['processed'] += 1
            try:
                print(f"\n[{stats['processed']}/{len(md_files)}] Procesando: {md_file.relative_to(source_dir)}")
                
                doc_data = parse_markdown_file(md_file)
                
                # Verificar si ya existe
                existing = db.query(Documento).filter(Documento.correlativo == doc_data['correlativo']).first()
                if existing:
                    print(f"  ⏭️  Ya existe: {doc_data['correlativo']}")
                    stats['skipped'] += 1
                    continue
                
                if dry_run:
                    print(f"  🔍 DRY-RUN: Insertaría {doc_data['correlativo']} - {doc_data['asunto'][:60]}")
                    stats['inserted'] += 1
                    continue
                
                # Crear documento
                documento = Documento(
                    id=uuid.uuid4(),
                    **doc_data,
                    confirmado_en=datetime.utcnow(),
                    confirmado_por=None,  # Sin usuario específico para migración
                )
                
                db.add(documento)
                db.commit()
                
                print(f"  ✅ Insertado: {doc_data['correlativo']}")
                stats['inserted'] += 1
                
            except Exception as e:
                print(f"  ❌ Error procesando {md_file.name}: {e}")
                stats['errors'] += 1
                db.rollback()
                continue
        
        print(f"\n📊 Resumen: {stats}")
        return stats
        
    finally:
        db.close()


def ensure_base_data(db: Session):
    """Asegurar que existan oficinas, tipos y personas básicas."""
    
    # Oficinas
    for sigla, nombre in OFICINAS_CONOCIDAS.items():
        existing = db.query(Oficina).filter(Oficina.sigla == sigla).first()
        if not existing:
            db.add(Oficina(sigla=sigla, nombre=nombre, activa=True))
    
    # Tipos de documento
    tipos_base = [
        ('MEMO', 'Memorándum', '{oficina}-MEMO', 5, False),
        ('OFICIO', 'Oficio', '{oficina}-OFI', 10, False),
        ('CIRCULAR', 'Circular', '{oficina}-CIR', 3, False),
        ('INFORME', 'Informe', '{oficina}-INF', 15, True),
        ('NOTA', 'Nota / Nota de Entrega', '{oficina}-NOTA', 2, False),
        ('ACTA', 'Acta', '{oficina}-ACTA', 0, True),
        ('RESOLUCION', 'Resolución', '{oficina}-RES', 0, False),
        ('SOLICITUD', 'Solicitud', '{oficina}-SOL', 10, False),
        ('RECIBO', 'Recibo', '{oficina}-REC', 0, False),
        ('OTRO', 'Otro tipo de documento', '{oficina}-OTR', 5, False),
    ]
    
    for codigo, nombre, prefijo, plazo, anexos in tipos_base:
        existing = db.query(TipoDocumento).filter(TipoDocumento.codigo == codigo).first()
        if not existing:
            db.add(TipoDocumento(
                codigo=codigo,
                nombre=nombre,
                prefijo_correlativo=prefijo,
                regla_secuencial={"formato": f"{prefijo}-{{año}}-{{secuencial:04d}}", "reinicio_anual": True},
                plazo_dias_respuesta=plazo,
                requiere_anexos=anexos,
                activo=True,
            ))
    
    db.commit()


def main():
    parser = argparse.ArgumentParser(description='Migrar documentos históricos .md')
    parser.add_argument('--source-dir', default='./informes',
                        help='Directorio con archivos .md')
    parser.add_argument('--dry-run', action='store_true',
                        help='Solo mostrar qué se haría sin insertar')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limitar número de archivos a procesar (0 = sin límite)')
    
    args = parser.parse_args()
    
    source_dir = Path(args.source_dir)
    
    print("🚀 Iniciando migración de documentos históricos")
    print(f"📂 Origen: {source_dir}")
    print(f"🔍 Dry-run: {args.dry_run}")
    
    stats = migrate_historical_docs(source_dir, dry_run=args.dry_run)
    
    print("\n" + "="*50)
    print("📊 RESUMEN FINAL")
    print("="*50)
    print(f"Procesados: {stats['processed']}")
    print(f"Insertados: {stats['inserted']}")
    print(f"Omitidos:   {stats['skipped']}")
    print(f"Errores:    {stats['errors']}")


if __name__ == '__main__':
    main()