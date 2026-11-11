#!/usr/bin/env bash
# Резервное копирование данных «Домашнего склада» на VPS.
#
# POST /api/backup хранит копии РЯДОМ с файлом данных — на том же диске:
# при сбое диска пропадают и данные, и копии. Этот скрипт складывает tar-архивы
# каталога ./data в другой каталог (по умолчанию /var/backups/home-storage);
# удерживаются последние BACKUP_KEEP архивов.
#
# Установка cron (ежедневно в 03:15): crontab -e
#   15 3 * * * /opt/home-storage/deploy/backup.sh >> /var/log/home-storage-backup.log 2>&1
#
# Дополнительно выгружайте архивы вне VPS (S3, другой сервер, локальная машина):
#   scp user@vps:/var/backups/home-storage/home-storage-*.tar.gz ./backups/

set -euo pipefail

# Каталог с данными относительно расположения скрипта (deploy/.. → корень проекта).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"
DEST_DIR="${BACKUP_DIR:-/var/backups/home-storage}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"

STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$DEST_DIR/home-storage-$STAMP.tar.gz"

if [ ! -d "$DATA_DIR" ]; then
    echo "Каталог данных не найден: $DATA_DIR" >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
tar -czf "$TARGET" -C "$DATA_DIR" .
chmod 600 "$TARGET"

# Оставляем последние BACKUP_KEEP архивов, старые удаляем (ошибка удаления
# отдельного файла не проваливает бэкап).
ls -1t "$DEST_DIR"/home-storage-*.tar.gz 2>/dev/null | tail -n +$((BACKUP_KEEP + 1)) | while IFS= read -r stale; do
    rm -f "$stale" || true
done

echo "Копия создана: $TARGET"
