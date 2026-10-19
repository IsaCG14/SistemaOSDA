#!/usr/bin/env bash
# scripts/backup.sh - Backup diario Supabase + volúmenes
# Ejecutado por servicio backup en docker-compose (cron 02:00)

set -euo pipefail

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

echo "=== BACKUP INICIADO: $DATE ==="

# 1. Backup PostgreSQL (schema + data)
echo "Dumping PostgreSQL..."
pg_dump -h db -U postgres -d postgres \
    --no-owner --no-privileges \
    --format=custom --compress=9 \
    --file="$BACKUP_DIR/supabase_$DATE.dump"

# También SQL plano para legibilidad
pg_dump -h db -U postgres -d postgres \
    --no-owner --no-privileges \
    | gzip > "$BACKUP_DIR/supabase_$DATE.sql.gz"

# 2. Backup volúmenes críticos (tar)
echo "Backing up volumes..."
tar -czf "$BACKUP_DIR/volumes_$DATE.tar.gz" -C /var/lib/postgresql/data . 2>/dev/null || true

# 3. Backup configuración (docker-compose, .env, scripts)
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    /docker-compose.yml /docker-compose.dev.yml /.env /scripts /supabase 2>/dev/null || true

# 4. Limpieza retención
echo "Limpiando backups > $RETENTION_DAYS días..."
find "$BACKUP_DIR" -name "supabase_*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "supabase_*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "volumes_*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "config_*.tar.gz" -mtime +$RETENTION_DAYS -delete

# 5. Reporte
LATEST=$(ls -t "$BACKUP_DIR"/supabase_*.sql.gz 2>/dev/null | head -1)
SIZE=$(du -h "$LATEST" | cut -f1)
echo "✅ Backup completado: $LATEST ($SIZE)"
echo "=== BACKUP FINALIZADO ==="