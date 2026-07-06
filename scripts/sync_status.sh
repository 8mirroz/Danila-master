#!/usr/bin/env bash
# sync_status.sh – обновляет статус проекта в DM obs/00-overview.md и ведёт лог в DM obs/obsidian_sync.log

set -euo pipefail

# Путь к файлам (абсолютные для надежности на macOS)
ROOT="/Users/user/projects/Danila master"
MANIFEST="$ROOT/partsops_agent_os_devpack/00_SYSTEM/SYSTEM_MANIFEST.yaml"
OVERVIEW="$ROOT/DM obs/00-overview.md"
LOGFILE="$ROOT/DM obs/obsidian_sync.log"

# Получить current_stage, если существует, иначе fallback к discovery
if grep -e "current_stage" "$MANIFEST" > /dev/null 2>&1; then
  STAGE=$(grep -e "current_stage" "$MANIFEST" | awk -F": " '{print $2}' | tr -d "[:space:]")
else
  STAGE="discovery"
fi

# Текущая дата‑время в ISO8601 (UTC)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Обновить строку Last Sync в overview
# Используем grep -e для совместимости с BSD grep на macOS
ORIG_LINE=$(grep -e "- Last Sync:" "$OVERVIEW" | grep -n "" | cut -d: -f1 | head -n 1 || true)

if [[ -n "$ORIG_LINE" ]]; then
  # В macOS sed -i '' требует, что команда замены будет отделена от адреса строки
  # Формат: sed -i '' 'line_num s/old/new/' file
  sed -i '' "${ORIG_LINE}s|`.*`|`$NOW`|" "$OVERVIEW"
else
  INSERT_AFTER=$(grep -e "- Current Stage:" "$OVERVIEW" | grep -n "" | cut -d: -f1 | head -n 1 || true)
  if [[ -n "$INSERT_AFTER" ]]; then
    NEXT=$((INSERT_AFTER + 1))
    sed -i '' "${NEXT}i- Last Sync: \`$NOW\`" "$OVERVIEW"
  fi
fi

# Обновить Current Stage в overview
CURRENT_LINE=$(grep -e "- Current Stage:" "$OVERVIEW" | grep -n "" | cut -d: -f1 | head -n 1 || true)
if [[ -n "$CURRENT_LINE" ]]; then
  sed -i '' "${CURRENT_LINE}s|`.*`|`$STAGE`|" "$OVERVIEW"
fi

# Мини‑лог: запись в файл
echo "[$NOW] Sync: set current_stage=$STAGE" >> "$LOGFILE"

echo "Sync completed. Current stage: $STAGE, timestamp: $NOW"
