#!/usr/bin/env bash
# Small curl helper that reuses a fixed session_id so all turns land in one log.
#
# Usage:
#   ./scripts/curl_fixed_session.sh [audio|text]
#
# Env vars:
#   BASE_URL       Default: http://localhost:18000
#   CHARACTER_ID   Default: 6
#   SID            Default: curl-<timestamp>
#
# Examples:
#   BASE_URL=http://localhost:18000 ./scripts/curl_fixed_session.sh audio
#   SID=my-demo-123 CHARACTER_ID=6 ./scripts/curl_fixed_session.sh text

set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:18000}
CHARACTER_ID=${CHARACTER_ID:-6}
SID=${SID:-"curl-$(date +%Y%m%d%H%M%S)"}
MODE=${1:-audio} # audio or text

echo "Using BASE_URL=$BASE_URL CHARACTER_ID=$CHARACTER_ID SID=$SID MODE=$MODE"

if [[ "$MODE" == "audio" ]]; then
  # 5-turn audio using assets/01..05.mp3
  for i in 01 02 03 04 05; do
    FILE="assets/${i}.mp3"
    if [[ ! -f "$FILE" ]]; then
      echo "Missing file: $FILE" >&2
      exit 1
    fi
    echo "\nTurn ${i} → $FILE"
    curl -sS \
      -F "audio_file=@${FILE}" \
      -F "character_id=${CHARACTER_ID}" \
      -F "session_id=${SID}" \
      "${BASE_URL}/api/dialogue/audio"
    echo
  done

elif [[ "$MODE" == "text" ]]; then
  # 10-turn memory probe (same prompts as test_memory_probe_10)
  declare -a TURNS=(
    "你好，感覺怎麼樣？"
    "有沒有覺得發燒或不舒服？"
    "你目前正在使用的藥名、劑量與服用頻次是什麼？請清楚說明。"
    "從什麼時候開始的？"
    "還有其他症狀嗎？"
    "昨晚睡眠品質如何？"
    "今天活動量大概多少？"
    "目前飲食有沒有不舒服的地方？"
    "請你再次清楚說明之前提到的藥名、劑量與服用頻次；若不確定請直接說不確定。"
    "請逐字重述你先前說過的藥名、劑量與服用頻次（若不確定請直接說不確定）。"
  )
  idx=0
  for t in "${TURNS[@]}"; do
    idx=$((idx+1))
    echo -e "\nTurn ${idx}: $t"
    body=$(printf '{"text":"%s","character_id":"%s","session_id":"%s"}' "$t" "$CHARACTER_ID" "$SID")
    curl -sS -H 'Content-Type: application/json' -d "$body" "${BASE_URL}/api/dialogue/text"
    echo
  done

else
  echo "Unknown MODE: $MODE (use 'audio' or 'text')" >&2
  exit 1
fi

echo -e "\nSession summary for SID=${SID}:"
curl -sS "${BASE_URL}/api/dev/session/${SID}/history" || true

