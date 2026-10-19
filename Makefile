# Makefile - Office Secretary Document Agent
# Uso: make <target>

.PHONY: help up down restart logs status health migrate seed test backup restore resume clean

# Variables
COMPOSE_FILES = -f docker-compose.yml
ifeq ($(ENV),dev)
    COMPOSE_FILES += -f docker-compose.dev.yml
    PROFILE = dev
else
    PROFILE = prod
endif

DC = docker compose $(COMPOSE_FILES) --profile $(PROFILE)

# ─────────────────────────────────────────────────────────────────
# AYUDA
# ─────────────────────────────────────────────────────────────────
help:
	@echo "Office Secretary Document Agent - Comandos disponibles:"
	@echo ""
	@echo "  Inicialización:"
	@echo "    make init              - Crear .env desde .env.example, pull images"
	@echo "    make setup             - init + up + migrate + seed + health"
	@echo ""
	@echo "  Ciclo de vida:"
	@echo "    make up                - Levantar stack (detached)"
	@echo "    make down              - Bajar stack"
	@echo "    make restart           - Reiniciar stack"
	@echo "    make logs [svc=]       - Ver logs (opcional svc=backend)"
	@echo "    make status            - Estado contenedores"
	@echo "    make health            - Healthchecks completos"
	@echo ""
	@echo "  Base de datos:"
	@echo "    make migrate           - Ejecutar migraciones (alembic)"
	@echo "    make migrate-status    - Estado migraciones"
	@echo "    make seed              - Cargar datos semilla (oficinas, tipos)"
	@echo "    make shell-db          - psql en supabase-db"
	@echo ""
	@echo "  Desarrollo:"
	@echo "    make dev-up            - Levantar en modo dev (ENV=dev)"
	@echo "    make dev-down          - Bajar modo dev"
	@echo "    make dev-logs [svc=]   - Logs modo dev"
	@echo "    make backend-shell     - Shell en backend contenedor"
	@echo "    make bot-shell         - Shell en bot contenedor"
	@echo ""
	@echo "  Testing:"
	@echo "    make test              - Tests unitarios + integración"
	@echo "    make test-backend      - Tests backend only"
	@echo "    make test-bot          - Tests bot only"
	@echo "    make test-frontend     - Tests frontend only"
	@echo "    make lint              - Lint (ruff, mypy, eslint)"
	@echo ""
	@echo "  Backup / Recuperación:"
	@echo "    make backup            - Backup manual inmediato"
	@echo "    make restore FILE=     - Restaurar desde backup (FILE=path)"
	@echo "    make resume            - Reanudación segura tras corte"
	@echo ""
	@echo "  Mantenimiento:"
	@echo "    make pull              - Actualizar imágenes"
	@echo "    make clean             - Limpiar volúmenes NO persistentes"
	@echo "    make prune             - Limpiar todo (CUIDADO: borra datos)"

# ─────────────────────────────────────────────────────────────────
# INICIALIZACIÓN
# ─────────────────────────────────────────────────────────────────
init:
	@test -f .env || cp .env.example .env
	@echo "✅ .env creado. Edítalo con valores reales antes de continuar."
	@$(DC) pull

setup: init up migrate seed health
	@echo "✅ Setup completo. Sistema listo en https://localhost (prod) o http://localhost:8080 (dev)"

# ─────────────────────────────────────────────────────────────────
# CICLO DE VIDA
# ─────────────────────────────────────────────────────────────────
up:
	@$(DC) up -d --remove-orphans
	@echo "⏳ Esperando healthchecks..."
	@sleep 10
	@make health

down:
	@$(DC) down --remove-orphans

restart: down up

logs:
	@$(DC) logs -f $(if $(svc),$(svc),)

status:
	@$(DC) ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}\t{{.Ports}}"

health:
	@echo "=== Healthchecks ==="
	@for svc in supabase-db supabase-kong supabase-auth supabase-storage graphify ollama backend telegram-bot; do \
		echo -n "$$svc: "; \
		docker inspect --format='{{.State.Health.Status}}' osda-$$svc 2>/dev/null || echo "no container"; \
	done
	@echo ""
	@echo "=== Conectividad ==="
	@docker exec osda-backend curl -sf http://supabase-kong:8000/health 2>/dev/null && echo "Backend → Kong: OK" || echo "Backend → Kong: FAIL"
	@docker exec osda-backend curl -sf http://graphify:8080/health 2>/dev/null && echo "Backend → Graphify: OK" || echo "Backend → Graphify: FAIL"
	@docker exec osda-backend curl -sf http://ollama:11434/api/tags 2>/dev/null && echo "Backend → Ollama: OK" || echo "Backend → Ollama: FAIL"

# ─────────────────────────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────────────────────────
migrate:
	@$(DC) run --rm migrator alembic upgrade head

migrate-status:
	@$(DC) run --rm migrator alembic current

migrate-create:
	@read -p "Mensaje migración: " msg; \
	$(DC) run --rm migrator alembic revision --autogenerate -m "$$msg"

seed:
	@$(DC) run --rm migrator python -m scripts.seed_data

shell-db:
	@docker exec -it osda-supabase-db psql -U postgres -d postgres

# ─────────────────────────────────────────────────────────────────
# DESARROLLO
# ─────────────────────────────────────────────────────────────────
dev-up:
	@ENV=dev make up

dev-down:
	@ENV=dev make down

dev-logs:
	@ENV=dev make logs svc=$(svc)

dev-restart:
	@ENV=dev make restart

backend-shell:
	@docker exec -it osda-backend bash

bot-shell:
	@docker exec -it osda-telegram-bot bash

frontend-shell:
	@docker exec -it osda-frontend sh

# ─────────────────────────────────────────────────────────────────
# TESTING
# ─────────────────────────────────────────────────────────────────
test: test-backend test-bot test-frontend

test-backend:
	@$(DC) run --rm backend pytest -v --tb=short

test-bot:
	@$(DC) run --rm telegram-bot pytest -v --tb=short

test-frontend:
	@$(DC) run --rm frontend npm test -- --run

lint:
	@$(DC) run --rm backend ruff check app/
	@$(DC) run --rm backend mypy app/
	@$(DC) run --rm frontend npm run lint

# ─────────────────────────────────────────────────────────────────
# BACKUP / RECUPERACIÓN
# ─────────────────────────────────────────────────────────────────
backup:
	@$(DC) run --rm backup

restore:
	@test -n "$(FILE)" || (echo "Uso: make restore FILE=backups/supabase_20260817_020000.sql.gz" && exit 1)
	@echo "⚠️  Restaurando desde $(FILE) - Esto SOBRESCRIBE la BD actual."
	@read -p "¿Continuar? (s/N): " confirm && [ "$$confirm" = "s" ]
	@gunzip -c $(FILE) | docker exec -i osda-supabase-db psql -U postgres -d postgres

resume:
	@bash scripts/resume.sh

# ─────────────────────────────────────────────────────────────────
# MANTENIMIENTO
# ─────────────────────────────────────────────────────────────────
pull:
	@$(DC) pull

clean:
	@docker system prune -f --volumes --filter "label!=persist"

prune:
	@echo "⚠️  ELIMINA TODOS LOS DATOS (volúmenes persistentes incluidos)"
	@read -p "¿Seguro? Escribe 'BORRAR TODO' para confirmar: " confirm && [ "$$confirm" = "BORRAR TODO" ]
	@$(DC) down -v --remove-orphans
	@docker volume prune -f