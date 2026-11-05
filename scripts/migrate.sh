#!/usr/bin/env bash
# scripts/migrate.sh - Script para gestionar migraciones Alembic

set -euo pipefail

cd "$(dirname "$0")/../backend"

case "${1:-}" in
    "upgrade")
        echo "🔄 Ejecutando migraciones (upgrade)..."
        alembic upgrade head
        echo "✅ Migraciones completadas"
        ;;
    "downgrade")
        REV="${2:- -1}"
        echo "🔄 Revertiendo migración a $REV..."
        alembic downgrade "$REV"
        echo "✅ Rollback completado"
        ;;
    "current" | "status")
        echo "📋 Estado actual de migraciones:"
        alembic current
        ;;
    "history")
        echo "📜 Historial de migraciones:"
        alembic history
        ;;
    "create")
        if [ -z "${2:-}" ]; then
            echo "Uso: $0 create \"mensaje de la migración\""
            exit 1
        fi
        echo "📝 Creando nueva migración: $2"
        alembic revision --autogenerate -m "$2"
        ;;
    "seed")
        echo "🌱 Cargando datos semilla..."
        python -m scripts.seed_data
        ;;
    "reset")
        echo "⚠️  ADVERTENCIA: Esto eliminará todos los datos."
        read -p "¿Continuar? (s/N): " confirm
        if [ "$confirm" = "s" ]; then
            alembic downgrade base
            alembic upgrade head
            python -m scripts.seed_data
            echo "✅ Base de datos reiniciada con seed"
        else
            echo "Cancelado"
        fi
        ;;
    *)
        echo "Uso: $0 {upgrade|downgrade|current|history|create|seed|reset}"
        echo ""
        echo "Comandos:"
        echo "  upgrade           - Aplicar migraciones pendientes"
        echo "  downgrade <rev>   - Revertir a revisión (default: -1)"
        echo "  current|status    - Ver estado actual"
        echo "  history           - Ver historial"
        echo "  create \"msg\"      - Crear nueva migración"
        echo "  seed              - Cargar datos semilla"
        echo "  reset             - Resetear BD y recargar seed"
        exit 1
        ;;
esac