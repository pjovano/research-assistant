#!/usr/bin/env bash
set -uo pipefail

readonly STATE_DIR="$HOME/.research-vault"
readonly BUILT_MARK="$STATE_DIR/cloud-setup.done"
readonly LOG="$STATE_DIR/cloud-setup.log"
readonly REPORTED_LINES=20

is_cloud_session_without_environment() {
  [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && [ ! -e "$BUILT_MARK" ]
}

build_environment() {
  mkdir -p "$STATE_DIR"
  bash "$(dirname "${BASH_SOURCE[0]}")/cloud-setup.sh" > "$LOG" 2>&1
}

report_failure() {
  echo "The cloud setup failed; the last lines of $LOG:" >&2
  tail -n "$REPORTED_LINES" "$LOG" >&2
}

main() {
  is_cloud_session_without_environment || exit 0
  build_environment || { report_failure; exit 1; }
}

main "$@"
