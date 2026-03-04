#!/bin/bash
# Backward-compatible wrapper: delegate to Python generator.
# Usage: ./generate-digest.sh [daily|4h|weekly|monthly]

set -euo pipefail

DIGEST_TYPE="${1:-daily}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load local .env automatically for cron/manual runs.
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
  set +a
fi

exec python3 "$SCRIPT_DIR/generate-digest.py" "$DIGEST_TYPE"
