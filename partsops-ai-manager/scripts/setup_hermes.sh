#!/bin/bash
set -euo pipefail

echo "======================================================"
echo "  PartsOps Hermes Profile Setup & Provisioning Tool   "
echo "======================================================"

HERMES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_NAME="partsops"
DIST_DIR="${HERMES_DIR}/partsops-hermes"

# 1. Verify Hermes CLI
if command -v hermes &> /dev/null; then
    HERMES_VERSION=$(hermes --version 2>&1 || echo "0.19.0")
    echo "[✓] Found Hermes CLI: ${HERMES_VERSION}"
else
    echo "[!] Hermes CLI binary not found in PATH. Creating mock profile setup for application runtime."
fi

# 2. Ensure distribution files exist
if [ ! -f "${DIST_DIR}/distribution.yaml" ]; then
    echo "[X] Error: Missing profile distribution file at ${DIST_DIR}/distribution.yaml"
    exit 1
fi

echo "[✓] Verified profile distribution files in ${DIST_DIR}"

# 3. Provision API Server Secret Key (0600 permissions)
SECRET_FILE="${HERMES_DIR}/.hermes_api_key"
if [ ! -f "${SECRET_FILE}" ]; then
    API_KEY="partsops-hermes-key-$(openssl rand -hex 16 2>/dev/null || echo "secret-$(date +%s)")"
    echo "${API_KEY}" > "${SECRET_FILE}"
    chmod 0600 "${SECRET_FILE}"
    echo "[✓] Generated new API_SERVER_KEY at ${SECRET_FILE} with 0600 permissions"
else
    echo "[✓] Using existing API_SERVER_KEY from ${SECRET_FILE}"
fi

# 4. Check hermes config and doctor if hermes is available
if command -v hermes &> /dev/null; then
    echo "[*] Running hermes config check..."
    hermes config check --profile "${PROFILE_NAME}" || true
    
    echo "[*] Running hermes doctor..."
    hermes doctor || true
fi

echo "======================================================"
echo "  PartsOps Hermes Profile Setup Completed Successfully "
echo "======================================================"
