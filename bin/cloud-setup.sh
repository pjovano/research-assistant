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

trust_gateway_certificate() {
  [ -n "${CCR_AGENT_PROXY_CA_CERT_B64:-}" ] || return 0
  printf '%s' "$CCR_AGENT_PROXY_CA_CERT_B64" | base64 -d > "$GATEWAY_CERTIFICATE"
  update-ca-certificates > /dev/null
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

point_at_empty_vault() {
  mkdir -p "$EMPTY_VAULT/research vault"
  printf '{"vault_dir": "~/.research-vault/empty-vault"}\n' > "$STATE_DIR/machine.json"
}

install_pandoc() {
  local package="pandoc-${PANDOC_VERSION}-1-amd64.deb"
  curl -LsSf -o "/tmp/$package" "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/$package"
  dpkg -i "/tmp/$package"
}

prefetch_tokenizer() {
  mkdir -p "$TIKTOKEN_CACHE_DIR"
  "$VENV/bin/python" -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
}

main() {
  trust_gateway_certificate
  install_uv
  build_venv
  point_at_empty_vault
  install_pandoc
  prefetch_tokenizer
  node --version
  touch "$BUILT_MARK"
}

main "$@"
