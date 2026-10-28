#!/bin/bash
# scripts/backup.sh - Backup diario Supabase (postgres) + config
# Ejecutado por cron del host (02:00) o por el boton del dashboard
# (POST /api/backup/ejecutar). Detecta el entorno:
#   - HOST: usa docker exec (trust local en el contenedor de BD)
#   - CONTENEDOR backend: usa pg_dump/psql directos con la password del env
#
# Genera:
#   1. dump custom (.dump)  -> restauracion precisa con pg_restore
#   2. SQL plano (.sql.gz)  -> legible / restaurable con psql
#   3. config (.tar.gz)    -> compose + .env.example + scripts + supabase
#
# NO incluye el .env real (contiene secretos).

set -euo pipefail

BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)

# Detectar entorno
if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1 2>&1; then
    ENTORNO="host"
    BACKUP_DIR="${BACKUP_DIR:-/home/openclaw/office-secretary-document-agent/backups}"
    PROJECT_DIR="${PROJECT_DIR:-/home/openclaw/office-secretary-document-agent}"
else
    ENTORNO="contenedor"
    BACKUP_DIR="${BACKUP_DIR:-/backups}"
    PROJECT_DIR="${PROJECT_DIR:-/scripts/..}"
fi

mkdir -p "$BACKUP_DIR"

echo "=== BACKUP INICIADO: $DATE (entorno: $ENTORNO) ==="

dump_custom() {
    if [ "$ENTORNO" = "host" ]; then
        docker exec osda-supabase-db pg_dump -U postgres -d postgres \
            --no-owner --no-privileges --format=custom --compress=9 \
            --file="/tmp/supabase_$DATE.dump"
        docker cp "osda-supabase-db:/tmp/supabase_$DATE.dump" "$BACKUP_DIR/supabase_$DATE.dump"
        docker exec osda-supabase-db rm -f "/tmp/supabase_$DATE.dump"
    else
        PGPASSWORD="$SUPABASE_DB_PASSWORD" pg_dump -h supabase-db -U postgres -d postgres \
            --no-owner --no-privileges --format=custom --compress=9 \
            --file="$BACKUP_DIR/supabase_$DATE.dump"
    fi
}

dump_sql() {
    if [ "$ENTORNO" = "host" ]; then
        docker exec osda-supabase-db pg_dump -U postgres -d postgres \
            --no-owner --no-privileges > "$BACKUP_DIR/supabase_$DATE.sql"
    else
        PGPASSWORD="$SUPABASE_DB_PASSWORD" pg_dump -h supabase-db -U postgres -d postgres \
            --no-owner --no-privileges > "$BACKUP_DIR/supabase_$DATE.sql"
    fi
    gzip -f "$BACKUP_DIR/supabase_$DATE.sql"
}

# 1. Dump custom
echo "Dumping PostgreSQL (custom)..."
dump_custom
SIZE=$(stat -c%s "$BACKUP_DIR/supabase_$DATE.dump" 2>/dev/null || echo 0)
if [ "${SIZE:-0}" -lt 1024 ]; then
    echo "ERROR: dump sospechosamente pequeno ($SIZE bytes). Abortando."
    rm -f "$BACKUP_DIR/supabase_$DATE.dump"
    exit 1
fi
echo "  dump custom: $(du -h "$BACKUP_DIR/supabase_$DATE.dump" | cut -f1)"

# 2. SQL plano
echo "Dumping PostgreSQL (SQL plano)..."
dump_sql
echo "  sql.gz: $(du -h "$BACKUP_DIR/supabase_$DATE.sql.gz" | cut -f1)"

# 3. Config (solo en host: en contenedor no estan todos los archivos)
if [ "$ENTORNO" = "host" ]; then
    echo "Backupeando configuracion..."
    tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
        -C "$PROJECT_DIR" \
        docker-compose.yml docker-compose.dev.yml .env.example scripts supabase Makefile 2>/dev/null || true
    echo "  config: $(du -h "$BACKUP_DIR/config_$DATE.tar.gz" | cut -f1)"
fi

# 4. Limpieza por retencion
echo "Limpiando backups > $BACKUP_RETENTION_DAYS dias..."
find "$BACKUP_DIR" -name "supabase_*.dump" -mtime +"$BACKUP_RETENTION_DAYS" -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "supabase_*.sql.gz" -mtime +"$BACKUP_RETENTION_DAYS" -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +"$BACKUP_RETENTION_DAYS" -delete 2>/dev/null || true

# 5. Reporte
echo "✅ Backup completado:"
ls -lh "$BACKUP_DIR" | grep "$DATE" || true
echo "=== BACKUP FINALIZADO: $DATE ==="
