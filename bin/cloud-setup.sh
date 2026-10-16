#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly STATE_DIR="$HOME/.research-vault"
readonly VENV="$STATE_DIR/venv"
readonly EMPTY_VAULT="$STATE_DIR/empty-vault"
readonly PANDOC_VERSION="3.12"
readonly PYTHON_VERSION="3.12"

export UV_TORCH_BACKEND=cpu
export TIKTOKEN_CACHE_DIR="$STATE_DIR/tiktoken"

install_uv() {
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
}

build_venv() {
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
  install_uv
  build_venv
  point_at_empty_vault
  install_pandoc
  prefetch_tokenizer
  node --version
}

main "$@"
