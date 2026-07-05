#!/usr/bin/env bash
# sync_status.sh – обновляет статус проекта в DM obs/00-overview.md и ведёт лог в DM obs/obsidian_sync.log
# Требования:
#   - current_stage берётся из partsops_agent_os_devpack/00_SYSTEM/SYSTEM_MANIFEST.yaml
#   - обновляется строка "- Last Sync: `...`" в 00-overview.md
#   - минимальный лог изменений сохраняется в DM obs/obsidian_sync.log

set -euo pipefail

# Путь к файлам (от корня проекта)
MANIFEST="$(dirname "$(realpath "$0")")/../partsops_agent_os_devpack/00_SYSTEM/SYSTEM_MANIFEST.yaml"
OVERVIEW="$(dirname "$(realpath "$0")")/../DM obs/00-overview.md"
LOGFILE="$(dirname "$(realpath "$0")")/../DM obs/obsidian_sync.log"

# Получить current_stage, если существует, иначе fallback к discovery
if grep -q "current_stage" "$MANIFEST"; then
  STAGE=$(grep "current_stage" "$MANIFEST" | awk -F": " '{print $2}' | tr -d "[:space:]")
else
  STAGE="discovery"
fi

# Текущая дата‑время в ISO8601 (UTC)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Обновить строку Last Sync в overview (по шаблону "- Last Sync: `...`")
ORIG_LINE=$(grep -n "- Last Sync:" "$OVERVIEW" | cut -d: -f1 || true)
if [[ -n "$ORIG_LINE" ]]; then
  sed -i "${ORIG_LINE}s|\`.*\`|\`$NOW\`|" "$OVERVIEW"
else
  # Если строки нет, вставляем после Current Stage
  INSERT_AFTER=$(grep -n "- Current Stage:" "$OVERVIEW" | cut -d: -f1)
  if [[ -n "$INSERT_AFTER" ]]; then
    NEXT=$((INSERT_AFTER + 1))
    sed -i "${NEXT}i- Last Sync: \`$NOW\`" "$OVERVIEW"
  fi
fi

# Обновить Current Stage в overview, если нужно
CURRENT_LINE=$(grep -n "- Current Stage:" "$OVERVIEW" | cut -d: -f1 || true)
if [[ -n "$CURRENT_LINE" ]]; then
  sed -i "${CURRENT_LINE}s|`.*`|`$STAGE`|" "$OVERVIEW"
fi

# Мини‑лог: запись в файл
echo "[$NOW] Sync: set current_stage=$STAGE" >> "$LOGFILE"

echo "Sync completed. Current stage: $STAGE, timestamp: $NOW"
