#!/usr/bin/env bash
# scripts/restore.sh - Restauración interactiva desde backup

set -euo pipefail

BACKUP_DIR="./backups"

echo "=== BACKUPS DISPONIBLES ==="
ls -lh "$BACKUP_DIR"/supabase_*.sql.gz 2>/dev/null | tail -20

echo ""
read -p "Archivo a restaurar (ej: supabase_20260817_020000.sql.gz): " FILE
FILE="$BACKUP_DIR/$FILE"

[[ -f "$FILE" ]] || { echo "❌ Archivo no existe"; exit 1; }

echo "⚠️  ADVERTENCIA: Esto SOBRESCRIBE la base de datos actual."
echo "   Base de datos: postgres en supabase-db"
echo "   Archivo: $FILE"
echo ""
read -p "Escribe 'RESTAURAR' para confirmar: " CONFIRM
[[ "$CONFIRM" == "RESTAURAR" ]] || { echo "Cancelado"; exit 1; }

echo "Deteniendo servicios que usan la BD..."
docker compose stop backend telegram-bot graphify migrator 2>/dev/null || true

echo "Restaurando..."
gunzip -c "$FILE" | docker exec -i osda-supabase-db psql -U postgres -d postgres

echo "Reiniciando servicios..."
docker compose start backend telegram-bot graphify migrator

echo "Verificando..."
sleep 5
make health

echo "✅ Restauración completada"