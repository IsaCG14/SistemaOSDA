#!/bin/bash
# scripts/backup.sh - Backup diario Supabase (postgres) + config
# Ejecutado por cron del host (02:00) - ver crontab del usuario openclaw
#
# Tres capas:
#   1. dump custom (.dump)  -> restauracion precisa con pg_restore
#   2. SQL plano (.sql.gz)  -> legible / restaurable con psql
#   3. config (.tar.gz)    -> compose + .env.example + scripts + supabase
#
# NO incluye el .env real (contiene secretos): respaldarlo aparte de
# forma segura si se desea.

set -euo pipefail

PROJECT_DIR="/home/openclaw/office-secretary-document-agent"
BACKUP_DIR="$PROJECT_DIR/backups"
DB_CONTAINER="osda-supabase-db"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

mkdir -p "$BACKUP_DIR"

echo "=== BACKUP INICIADO: $DATE ==="

# 1. Dump en formato custom (pg_restore) - via docker exec (usa trust local)
echo "Dumping PostgreSQL (custom)..."
docker exec "$DB_CONTAINER" pg_dump -U postgres -d postgres \
    --no-owner --no-privileges \
    --format=custom --compress=9 \
    --file="/tmp/supabase_$DATE.dump"
docker cp "$DB_CONTAINER:/tmp/supabase_$DATE.dump" "$BACKUP_DIR/supabase_$DATE.dump"
docker exec "$DB_CONTAINER" rm -f "/tmp/supabase_$DATE.dump"

# Verificar que el dump NO esta vacio (bug historico: dumps de 0 bytes)
SIZE=$(stat -c%s "$BACKUP_DIR/supabase_$DATE.dump")
if [ "$SIZE" -lt 1024 ]; then
    echo "ERROR: dump sospechosamente pequeno ($SIZE bytes). Abortando."
    rm -f "$BACKUP_DIR/supabase_$DATE.dump"
    exit 1
fi
echo "  dump custom: $(du -h "$BACKUP_DIR/supabase_$DATE.dump" | cut -f1)"

# 2. SQL plano legible
echo "Dumping PostgreSQL (SQL plano)..."
docker exec "$DB_CONTAINER" pg_dump -U postgres -d postgres \
    --no-owner --no-privileges \
    > "$BACKUP_DIR/supabase_$DATE.sql"
gzip -f "$BACKUP_DIR/supabase_$DATE.sql"
echo "  sql.gz: $(du -h "$BACKUP_DIR/supabase_$DATE.sql.gz" | cut -f1)"

# 3. Config (sin .env real)
echo "Backupeando configuracion..."
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    -C "$PROJECT_DIR" \
    docker-compose.yml docker-compose.dev.yml .env.example scripts supabase Makefile 2>/dev/null || true
echo "  config: $(du -h "$BACKUP_DIR/config_$DATE.tar.gz" | cut -f1)"

# 4. Limpieza por retencion
echo "Limpiando backups > $RETENTION_DAYS dias..."
find "$BACKUP_DIR" -name "supabase_*.dump" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name "supabase_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +"$RETENTION_DAYS" -delete

# 5. Reporte
LATEST="$BACKUP_DIR/supabase_$DATE.sql.gz"
echo "✅ Backup completado:"
ls -lh "$BACKUP_DIR" | grep "$DATE" || true
echo "=== BACKUP FINALIZADO: $DATE ==="
