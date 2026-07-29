#!/bin/bash
set -euo pipefail

# Guard the complete local runtime, not just the queue worker.  The directory
# creation is atomic on macOS/Linux and survives a shell crash as a stale
# marker that can be reclaimed after verifying its PID is gone.
PARTSOPS_RUNTIME_GUARD_DIR="${PARTSOPS_RUNTIME_GUARD_DIR:-${TMPDIR:-/tmp}/partsops-ai-manager-runtime.lock}"
PARTSOPS_RUNTIME_GUARD_HELD=0

runtime_guard_release() {
  if [ "${PARTSOPS_RUNTIME_GUARD_HELD}" != "1" ]; then
    return 0
  fi
  if [ -f "${PARTSOPS_RUNTIME_GUARD_DIR}/pid" ] && [ "$(cat "${PARTSOPS_RUNTIME_GUARD_DIR}/pid")" = "$$" ]; then
    rm -f "${PARTSOPS_RUNTIME_GUARD_DIR}/pid"
    rmdir "${PARTSOPS_RUNTIME_GUARD_DIR}" 2>/dev/null || true
  fi
  PARTSOPS_RUNTIME_GUARD_HELD=0
}

runtime_guard_acquire() {
  if mkdir "${PARTSOPS_RUNTIME_GUARD_DIR}" 2>/dev/null; then
    printf '%s\n' "$$" > "${PARTSOPS_RUNTIME_GUARD_DIR}/pid"
    PARTSOPS_RUNTIME_GUARD_HELD=1
  else
    local existing_pid=""
    if [ -f "${PARTSOPS_RUNTIME_GUARD_DIR}/pid" ]; then
      existing_pid="$(cat "${PARTSOPS_RUNTIME_GUARD_DIR}/pid" 2>/dev/null || true)"
    fi
    if [ -n "${existing_pid}" ] && kill -0 "${existing_pid}" 2>/dev/null; then
      echo "[!] PartsOps runtime is already guarded by PID ${existing_pid}." >&2
      echo "    Stop that runtime before starting another one." >&2
      return 1
    fi
    if [ -n "${existing_pid}" ]; then
      echo "[i] Removing stale runtime guard for dead PID ${existing_pid}."
      rm -f "${PARTSOPS_RUNTIME_GUARD_DIR}/pid"
      rmdir "${PARTSOPS_RUNTIME_GUARD_DIR}" 2>/dev/null || true
    else
      echo "[!] Runtime guard exists without a verifiable owner: ${PARTSOPS_RUNTIME_GUARD_DIR}" >&2
      echo "    Remove it manually only after confirming no PartsOps runtime is active." >&2
      return 1
    fi
    runtime_guard_acquire
  fi

  local port listener
  for port in ${PARTSOPS_RUNTIME_PORTS:-8642 8000 5173}; do
    listener="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "${listener}" ]; then
      echo "[!] Port ${port} is already in use; refusing duplicate runtime start." >&2
      echo "${listener}" >&2
      runtime_guard_release
      return 1
    fi
  done
}
