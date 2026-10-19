# Office Secretary Document Agent - Project Summary

## Project Overview
**Sistema de Gestión Documental y Soporte de Secretaría ("Agente Secretario")**
Para la oficina de tecnología de información y comunicación (OTIC) de la institución.

## Estado Actual (2026-08-18)

### ✅ Completado - Módulo 1: Infraestructura Base
- `docker-compose.yml` - Stack completo (13 servicios)
- `docker-compose.dev.yml` - Overrides para desarrollo
- `Caddyfile` / `Caddyfile.dev` - Reverse proxy
- `.env.example` - Plantilla variables de entorno
- `Makefile` - Comandos unificados
- `scripts/` - healthcheck.sh, resume.sh, backup.sh, restore.sh, migrate.sh, migrate_historical_docs.py
- `supabase/kong.yml` - Configuración Kong API Gateway
- `.hermes/project_state.json` - Estado máquina
- `docs/` - EXECUTION_STATE.md, PROJECT_PLAN.md, DECISIONS.md, OPEN_QUESTIONS.md, RISKS_AND_ASSUMPTIONS.md, RESUME_PLAYBOOK.md

### ✅ Completado - Módulo 2: Modelo de Datos y Migraciones (En progreso)
- `backend/alembic/env.py` - Configuración Alembic
- `backend/alembic.ini` - Configuración Alembic
- `backend/alembic/versions/001_initial.py` - Migración inicial completa
- `backend/app/db/base.py` - Base de datos y sesiones
- `backend/app/core/config.py` - Configuración Pydantic Settings
- `backend/app/models/__init__.py` - Modelos SQLAlchemy completos
- `backend/scripts/seed_data.py` - Datos semilla (oficinas, tipos, personas, documentos ejemplo)
- `backend/scripts/run_migrations.py` - Runner de migraciones
- `scripts/migrate.sh` - Script de migraciones
- `scripts/migrate_historical_docs.py` - ETL para históricos .md

### ✅ Completado - Backend Services
- `backend/app/services/vision_ocr.py` - Pipeline OCR con Ollama
- `backend/app/services/graphify_client.py` - Cliente Graphify
- `backend/app/main.py` - FastAPI principal
- `backend/Dockerfile` - Multi-stage (prod/dev/migrator)
- `backend/requirements.txt` - Dependencias

### ✅ Completado - Graphify Service
- `graphify/Dockerfile` - Servicio Graphify API
- `graphify/requirements.txt` - Dependencias
- `graphify/main.py` - API Graphify con Neo4j

### ✅ Completado - Telegram Bot
- `bot/Dockerfile` - Multi-stage
- `bot/requirements.txt` - Dependencias
- `bot/main.py` - Entry point
- `bot/handlers/telegram_handlers.py` - Handlers completos

### ⏳ En Progreso - Descarga de Imágenes Docker
| Imagen | Estado |
|--------|--------|
| postgres:15 | ✅ Descargada |
| kong:3.5 | ✅ Descargada |
| caddy:2.8-alpine | ✅ Descargada |
| supabase/gotrue:v2.165.0 | ✅ Descargada |
| supabase/realtime:v2.33.8 | ✅ Descargada |
| supabase/postgres-meta:v0.83.0 | ✅ Descargada |
| postgrest/postgrest:v14.12 | ✅ Descargada |
| darthsim/imgproxy:v3.9.0 | ✅ Descargada |
| **ollama/ollama:latest** | ⏳ **Descargando (2.6GB, muy lento)** |
| **neo4j:5.15-community** | ⏳ Pendiente |
| **postgres:15-alpine** | ⏳ Pendiente |
| **postgres:16-alpine** | ⏳ Pendiente |

### ⏳ Pendientes
- Módulo 3: Backend API completo
- Módulo 4: Bot Telegram + Ingesta
- Módulo 5: Pipeline Vision/OCR
- Módulo 6: Motor Graphify
- Módulo 7: Dashboard React
- Módulo 8: Integración y QA
- Módulo 9: Despliegue y Runbooks
- Módulo 10: Auditoría Final

## Próximos Pasos Inmediatos
1. **Esperar descarga de ollama/ollama:latest** (2.6GB, muy lento en CPU)
2. **Descargar neo4j:5.15-community, postgres:15-alpine, postgres:16-alpine**
3. **Levantar stack**: `make up`
4. **Verificar healthchecks**: `make health`
5. **Descargar modelo Vision**: `docker exec osda-ollama ollama pull qwen2-vl-7b`
6. **Ejecutar migraciones**: `make migrate`
7. **Cargar seed data**: `make seed`
8. **Inspeccionar históricos .md**: `ls -la <directorio-de-informes>/`

## Decisiones Técnicas Clave
| ID | Decisión |
|----|----------|
| DEC-001 | Correlativo: `PrefijoOficina-TipoDoc-Año-Secuencial` (ej. `OTIC-MEMO-2026-0001`) |
| DEC-002 | Oficina que envía asigna correlativo; sistema valida unicidad |
| DEC-003 | Vision API: Ollama local CPU-only (qwen2-vl-7b) - GPU Quadro K600 insuficiente |
| DEC-004 | 4 estados: `RECIBIDO` → `EN_TRAMITE` → `RESPONDIDO` / `ARCHIVADO` |
| DEC-005 | Roles: `ADMIN`, `SECRETARIO` - allow-list dinámica desde BD |
| DEC-006 | Catálogo oficinas dinámico con aprobación admin |
| DEC-007 | Retención indefinida en Supabase Storage |
| DEC-008 | Exportación mensual Excel (job cron) |
| DEC-009 | Migrar históricos `.md` ANTES de M2 seed |
| DEC-010 | Resiliencia sin UPS: checkpoints/doc + WAL archiving + `resume.sh` |

## Riesgos Críticos Identificados
| ID | Riesgo | Mitigación |
|----|--------|------------|
| RIE-003 | Corte eléctrico sin UPS | Checkpoints/doc + WAL archive + `fsync=on` + `resume.sh` |
| RIE-011 | Vision CPU-only lento (30-60s/img) | Timeouts generosos + batch nocturno + umbrales ajustados |
| RIE-013 | Grupo Telegram sin allow-list estricta | Allow-list dinámica desde BD + rate limiting Kong |

## Comandos Útiles
```bash
# Ver estado imágenes
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"

# Levantar stack (cuando imágenes listas)
cd office-secretary-document-agent
make init && make up

# Verificar health
make health

# Descargar modelo Vision
docker exec osda-ollama ollama pull qwen2-vl-7b

# Migraciones
make migrate
make seed

# Ver logs
make logs svc=backend
make logs svc=telegram-bot
```

## Estructura de Directorios
```
office-secretary-document-agent/
├── .hermes/project_state.json
├── docker-compose.yml
├── docker-compose.dev.yml
├── Caddyfile / Caddyfile.dev
├── .env.example
├── Makefile
├── alembic.ini
├── scripts/
│   ├── healthcheck.sh, resume.sh, backup.sh, restore.sh
│   ├── migrate.sh, migrate_historical_docs.py
├── docs/
├── backend/
│   ├── app/ (FastAPI, models, services)
│   ├── alembic/ (migraciones)
│   ├── scripts/ (seed, migraciones)
│   ├── Dockerfile, requirements.txt
├── bot/ (Telegram Bot)
├── graphify/ (Graphify API + Neo4j)
├── frontend/ (React + Vite + Tailwind - pendiente)
└── supabase/kong.yml
```