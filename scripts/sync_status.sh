#!/usr/bin/env bash
# Keep one implementation for macOS and other shells. The previous inline sed
# implementation evaluated Markdown backticks as shell substitutions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/scripts/sync_status.py"
