#!/usr/bin/env bash
set -euo pipefail

SRC_DIR_DEFAULT="/home/radxa/nas102/cubie-nas"
DEST_DIR_DEFAULT="/opt/cubie-nas"
SERVICE_NAME_DEFAULT="cubie-nas"

SRC_DIR="${SRC_DIR:-$SRC_DIR_DEFAULT}"
DEST_DIR="${DEST_DIR:-$DEST_DIR_DEFAULT}"
SERVICE_NAME="${SERVICE_NAME:-$SERVICE_NAME_DEFAULT}"
DRY_RUN="${DRY_RUN:-0}"
SKIP_RESTART="${SKIP_RESTART:-0}"

log() {
  printf '[deploy-safe] %s\n' "$*"
}

fail() {
  printf '[deploy-safe][ERROR] %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

usage() {
  cat <<'EOF'
Usage: scripts/deploy-safe.sh [--dry-run] [--skip-restart] [--src PATH] [--dest PATH] [--service NAME]

Safe deployment for Cubie NAS:
- Enforces rsync excludes for runtime artifacts (.env, .venv, __pycache__).
- Preserves runtime secrets and virtualenv in destination.
- Verifies systemd service reaches active state after restart.

Environment overrides:
  SRC_DIR, DEST_DIR, SERVICE_NAME, DRY_RUN=1, SKIP_RESTART=1
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --skip-restart)
      SKIP_RESTART=1
      shift
      ;;
    --src)
      SRC_DIR="$2"
      shift 2
      ;;
    --dest)
      DEST_DIR="$2"
      shift 2
      ;;
    --service)
      SERVICE_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

require_cmd rsync
require_cmd systemctl
require_cmd sudo

[[ -d "$SRC_DIR" ]] || fail "Source directory does not exist: $SRC_DIR"
[[ -d "$DEST_DIR" ]] || fail "Destination directory does not exist: $DEST_DIR"
[[ -f "$SRC_DIR/requirements.txt" ]] || fail "requirements.txt missing in source: $SRC_DIR"
[[ -f "$DEST_DIR/.env" ]] || fail "Destination .env missing at $DEST_DIR/.env (refusing deploy to avoid secret drift)."
[[ -d "$DEST_DIR/.venv" ]] || fail "Destination .venv missing at $DEST_DIR/.venv (refusing deploy to avoid runtime breakage)."
[[ -x "$DEST_DIR/.venv/bin/uvicorn" ]] || fail "Destination uvicorn missing at $DEST_DIR/.venv/bin/uvicorn"

RSYNC_ARGS=(
  -a
  --delete
  --exclude .git
  --exclude .env
  --exclude .venv/
  --exclude __pycache__/
)

if [[ "$DRY_RUN" == "1" ]]; then
  RSYNC_ARGS+=(--dry-run)
  log "Dry run enabled. No files will be modified."
fi

log "Deploying from $SRC_DIR to $DEST_DIR"
run_root rsync "${RSYNC_ARGS[@]}" "$SRC_DIR/" "$DEST_DIR/"

if [[ "$DRY_RUN" == "1" ]]; then
  log "Dry run complete."
  exit 0
fi

[[ -f "$DEST_DIR/.env" ]] || fail "Post-sync check failed: .env missing"
[[ -d "$DEST_DIR/.venv" ]] || fail "Post-sync check failed: .venv missing"
[[ -x "$DEST_DIR/.venv/bin/uvicorn" ]] || fail "Post-sync check failed: uvicorn missing"

if [[ "$SKIP_RESTART" == "1" ]]; then
  log "Skipping service restart by request."
  exit 0
fi

log "Restarting service: $SERVICE_NAME"
run_root systemctl restart "$SERVICE_NAME"

state="$(systemctl is-active "$SERVICE_NAME" || true)"
if [[ "$state" != "active" ]]; then
  run_root systemctl status "$SERVICE_NAME" --no-pager -l || true
  fail "Service failed to reach active state (current: $state)"
fi

log "Deployment successful. Service is active."
