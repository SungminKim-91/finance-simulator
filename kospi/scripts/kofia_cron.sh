#!/bin/bash
# KOFIA FreeSIS 자동 다운로드 cron wrapper
# crontab: 0 18 * * 1-5 /home/sungmin/finance-simulator/kospi/scripts/kofia_cron.sh
#
# 평일 KST 18:00 실행 (장 마감 후 데이터 확정)

set -euo pipefail

PROJECT_DIR="/home/sungmin/finance-simulator"
LOG_DIR="${PROJECT_DIR}/kospi/data/logs"
LOG_FILE="${LOG_DIR}/kofia_cron_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "=== KOFIA Auto Download: $(date) ===" >> "$LOG_FILE"

cd "${PROJECT_DIR}/kospi"
source "${PROJECT_DIR}/.venv/bin/activate"

python -m scripts.kofia_downloader --auto >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "=== Exit: ${EXIT_CODE} ===" >> "$LOG_FILE"

# 30일 이상 된 로그 정리
find "$LOG_DIR" -name "kofia_cron_*.log" -mtime +30 -delete 2>/dev/null || true
