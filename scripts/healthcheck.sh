#!/usr/bin/env bash
# scripts/healthcheck.sh - Healthcheck completo del stack
# Uso: ./scripts/healthcheck.sh [--json]

set -euo pipefail

JSON_OUTPUT=false
[[ "${1:-}" == "--json" ]] && JSON_OUTPUT=true

check_service() {
    local name=$1
    local url=$2
    local expected=${3:-200}
    local timeout=5
    
    if curl -sf -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null | grep -q "^$expected$"; then
        echo "healthy"
        return 0
    else
        echo "unhealthy"
        return 1
    fi
}

check_docker_health() {
    local container=$1
    docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "missing"
}

# Servicios a verificar
declare -A SERVICES=(
    ["supabase-db"]="docker"
    ["supabase-kong"]="http://localhost:8000/health"
    ["supabase-auth"]="http://localhost:9999/health"
    ["supabase-storage"]="http://localhost:5000/status"
    ["graphify"]="http://localhost:8080/health"
    ["ollama"]="http://localhost:11434/api/tags"
    ["backend"]="http://localhost:8001/health"
    ["telegram-bot"]="docker"
    ["frontend"]="http://localhost:8080"
    ["caddy"]="docker"
)

RESULTS=()
ALL_HEALTHY=true

for svc in "${!SERVICES[@]}"; do
    target=${SERVICES[$svc]}
    container="osda-$svc"
    
    if [[ "$target" == "docker" ]]; then
        status=$(check_docker_health "$container")
    else
        status=$(check_service "$svc" "$target")
    fi
    
    if [[ "$status" == "healthy" ]]; then
        RESULTS+=("$svc: ✅ healthy")
    else
        RESULTS+=("$svc: ❌ $status")
        ALL_HEALTHY=false
    fi
done

# Conectividad interna
if docker exec osda-backend curl -sf http://supabase-kong:8000/health >/dev/null 2>&1; then
    RESULTS+=("internal:backend→kong: ✅")
else
    RESULTS+=("internal:backend→kong: ❌")
    ALL_HEALTHY=false
fi

if docker exec osda-backend curl -sf http://graphify:8080/health >/dev/null 2>&1; then
    RESULTS+=("internal:backend→graphify: ✅")
else
    RESULTS+=("internal:backend→graphify: ❌")
    ALL_HEALTHY=false
fi

if docker exec osda-backend curl -sf http://ollama:11434/api/tags >/dev/null 2>&1; then
    RESULTS+=("internal:backend→ollama: ✅")
else
    RESULTS+=("internal:backend→ollama: ❌")
    ALL_HEALTHY=false
fi

# Output
if [[ "$JSON_OUTPUT" == true ]]; then
    jq -n --argjson healthy "$ALL_HEALTHY" --arg results "$(printf '%s\n' "${RESULTS[@]}")" \
        '{healthy: $healthy, checks: ($results | split("\n") | map(select(length>0)) | map(split(": ")) | map({service: .[0], status: .[1]}))}'
else
    printf '%s\n' "${RESULTS[@]}"
    echo ""
    if [[ "$ALL_HEALTHY" == true ]]; then
        echo "✅ ALL SYSTEMS HEALTHY"
        exit 0
    else
        echo "❌ SOME SYSTEMS UNHEALTHY"
        exit 1
    fi
fi