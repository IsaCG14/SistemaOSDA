#!/usr/bin/env bash
# scripts/resume.sh - Reanudación segura tras corte/interrupción
# Lee .hermes/project_state.json y continúa desde último checkpoint

set -euo pipefail

STATE_FILE=".hermes/project_state.json"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/resume_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG_FILE"; }

log "=== INICIANDO REANUDACIÓN SEGURA ==="

# 1. Verificar archivo de estado
if [[ ! -f "$STATE_FILE" ]]; then
    log "ERROR: No existe $STATE_FILE. No se puede reanudar automáticamente."
    exit 1
fi

CURRENT_PHASE=$(jq -r '.current_phase' "$STATE_FILE")
CURRENT_MODULE=$(jq -r '.current_module' "$STATE_FILE")
CURRENT_STEP=$(jq -r '.current_step' "$STATE_FILE")
STATUS=$(jq -r '.status' "$STATE_FILE")

log "Estado previo: phase=$CURRENT_PHASE module=$CURRENT_MODULE step=$CURRENT_STEP status=$STATUS"

# 2. Verificar Docker daemon
if ! docker info >/dev/null 2>&1; then
    log "ERROR: Docker daemon no responde"
    exit 1
fi

# 3. Levantar stack base si no está arriba
log "Verificando stack Docker..."
if ! docker compose ps --format "{{.Name}}" | grep -q "osda-supabase-db"; then
    log "Stack no está corriendo. Levantando..."
    make up
else
    log "Stack ya corriendo. Verificando health..."
    make health || log "WARN: Algunos servicios unhealthy, continuando..."
fi

# 4. Verificar migraciones
log "Verificando migraciones..."
make migrate-status 2>&1 | tee -a "$LOG_FILE" || log "WARN: No se pudo verificar migraciones"

# 5. Verificar Graphify
log "Verificando Graphify..."
curl -sf http://localhost:8080/health 2>&1 | tee -a "$LOG_FILE" || log "WARN: Graphify no responde"

# 6. Verificar Ollama + modelo Vision
log "Verificando Ollama + modelo $VISION_MODEL..."
MODEL_EXISTS=$(docker exec osda-ollama ollama list 2>/dev/null | grep -c "$VISION_MODEL" || echo 0)
if [[ "$MODEL_EXISTS" -eq 0 ]]; then
    log "Modelo $VISION_MODEL no encontrado. Descargando (puede tardar)..."
    docker exec osda-ollama ollama pull "$VISION_MODEL" 2>&1 | tee -a "$LOG_FILE"
else
    log "Modelo $VISION_MODEL presente ✅"
fi

# 7. Verificar último documento procesado (si aplica)
LAST_DOC=$(jq -r '.last_processed_document_id // "none"' "$STATE_FILE")
if [[ "$LAST_DOC" != "none" ]]; then
    log "Verificando último documento procesado: $LAST_DOC"
    # Query a Supabase para confirmar persistencia
    docker exec osda-supabase-db psql -U postgres -d postgres -t -c \
        "SELECT id, correlativo, estado, confirmado_en FROM documentos WHERE id = '$LAST_DOC';" 2>&1 | tee -a "$LOG_FILE"
fi

# 8. Actualizar estado a executing
jq '.status = "executing" | .updated_at_utc = now | .resume_instructions = "Ejecutado resume.sh - continuar desde current_step"' "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"

log "=== REANUDACIÓN COMPLETADA ==="
log "Próximo paso: $CURRENT_STEP"
log "Ejecutar: make dev-up (o make up) y continuar con el módulo actual"