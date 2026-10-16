#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly STATE_DIR="$HOME/.research-vault"
readonly VENV="$STATE_DIR/venv"
readonly EMPTY_VAULT="$STATE_DIR/empty-vault"
readonly PANDOC_VERSION="3.12"
readonly PYTHON_VERSION="3.12"
readonly BUILT_MARK="$STATE_DIR/cloud-setup.done"
readonly SYSTEM_CERTIFICATES="/etc/ssl/certs/ca-certificates.crt"
readonly GATEWAY_CERTIFICATE="/usr/local/share/ca-certificates/cloud-gateway.crt"

export UV_TORCH_BACKEND=cpu
export UV_NATIVE_TLS=1
export SSL_CERT_FILE="$SYSTEM_CERTIFICATES"
export REQUESTS_CA_BUNDLE="$SYSTEM_CERTIFICATES"
export TIKTOKEN_CACHE_DIR="$STATE_DIR/tiktoken"

FAILED_STEPS=""

route_unresolvable_hosts_through_gateway() {
  NO_PROXY="$(entries_reachable_without_gateway "${NO_PROXY:-}")"
  no_proxy="$NO_PROXY"
  export NO_PROXY no_proxy
}

entries_reachable_without_gateway() {
  local entries entry kept=""
  IFS=',' read -ra entries <<< "$1"
  for entry in ${entries[@]+"${entries[@]}"}; do
    if is_reachable_without_gateway "$entry"; then kept="${kept:+$kept,}$entry"; fi
  done
  printf '%s' "$kept"
}

is_reachable_without_gateway() {
  is_address "$1" || is_suffix_pattern "$1" || getent hosts "$1" > /dev/null
}

is_address() {
  [[ "$1" != *[!0-9A-Fa-f.:/]* ]]
}

is_suffix_pattern() {
  [[ "$1" == .* || "$1" == \** ]]
}

point_at_empty_vault() {
  mkdir -p "$EMPTY_VAULT/research vault"
  printf '{"vault_dir": "~/.research-vault/empty-vault"}\n' > "$STATE_DIR/machine.json"
}

trust_gateway_certificate() {
  [ -n "${CCR_AGENT_PROXY_CA_CERT_B64:-}" ] || return 0
  printf '%s' "$CCR_AGENT_PROXY_CA_CERT_B64" | base64 -d > "$GATEWAY_CERTIFICATE"
  update-ca-certificates > /dev/null
}

run_step() {
  local step="$1"
  local status
  set +e
  ( set -e; "$step" )
  status=$?
  set -e
  [ "$status" -eq 0 ] || record_failure "$step" "$status"
}

record_failure() {
  echo "cloud-setup: $1 failed with exit $2" >&2
  FAILED_STEPS="$FAILED_STEPS $1"
}

install_pandoc() {
  local package="pandoc-${PANDOC_VERSION}-1-amd64.deb"
  curl -LsSf -o "/tmp/$package" "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/$package"
  dpkg -i "/tmp/$package"
}

build_python_environment() {
  install_uv
  build_venv
  prefetch_tokenizer
}

install_uv() {
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
}

build_venv() {
  rm -rf "$VENV"
  uv venv --python "$PYTHON_VERSION" "$VENV"
  uv pip sync --python "$VENV/bin/python" "$REPOSITORY/requirements.lock"
}

prefetch_tokenizer() {
  mkdir -p "$TIKTOKEN_CACHE_DIR"
  "$VENV/bin/python" -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
}

require_node() {
  node --version
}

stop_unless_every_step_passed() {
  if [ -n "$FAILED_STEPS" ]; then
    echo "cloud-setup: the environment is not built; failed:$FAILED_STEPS" >&2
    exit 1
  fi
}

main() {
  route_unresolvable_hosts_through_gateway
  point_at_empty_vault
  trust_gateway_certificate
  run_step install_pandoc
  run_step build_python_environment
  run_step require_node
  stop_unless_every_step_passed
  touch "$BUILT_MARK"
}

main "$@"
