#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌸 tschan installer
# TeamSpeak 3 Template Generator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -euo pipefail

REPO_URL="https://github.com/meower1/TsChan.git"
MIN_PYTHON="3.10"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colors ──────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
PINK='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
    echo -e "${PINK}"
    cat << 'EOF'
    ╔══════════════════════════════════════╗
    ║                                      ║
    ║     🌸  tschan  🌸                   ║
    ║     TeamSpeak 3 Template Generator   ║
    ║                                      ║
    ╚══════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

info()  { echo -e "${CYAN}[info]${NC}  $*"; }
ok()    { echo -e "${GREEN}[✓]${NC}     $*"; }
err()   { echo -e "${RED}[✗]${NC}     $*" >&2; }
die()   { err "$@"; exit 1; }

warn_if_root() {
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
        info "Running as root. tschan will be installed for root and will manage /root/tschan-server."
    fi
}

# ── Checks ──────────────────────────────────
check_python() {
    local cmd=""
    for c in python3 python; do
        if command -v "$c" &>/dev/null; then
            local ver
            ver="$($c -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
            if $c -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                cmd="$c"
                ok "Python $ver found ($c)"
                break
            fi
        fi
    done
    if [ -z "$cmd" ]; then
        die "Python >= $MIN_PYTHON is required but not found. Install it first."
    fi
    PYTHON_CMD="$cmd"
}

check_docker() {
    if ! command -v docker &>/dev/null; then
        die "Docker is required but not found. Install Docker first: https://docs.docker.com/get-docker/"
    fi
    ok "Docker found ($(docker --version | head -1))"

    if ! docker compose version &>/dev/null; then
        die "Docker Compose v2 is required. Update Docker or install the compose plugin."
    fi
    ok "Docker Compose v2 found"
}

check_git() {
    if ! command -v git &>/dev/null; then
        die "Git is required but not found. Install git first."
    fi
    ok "Git found"
}

install_python_package() {
    if ./.venv/bin/pip install -q -e .; then
        return
    fi

    info "Default Python package index failed. Retrying with pypi.devneeds.ir..."
    PIP_INDEX_URL="https://pypi.devneeds.ir/simple/" \
    PIP_DEFAULT_TIMEOUT=60 \
        ./.venv/bin/pip install -q -e . \
        || die "Failed to install tschan package."
}

# ── Install ─────────────────────────────────
do_install() {
    print_banner

    info "Checking prerequisites..."
    warn_if_root
    check_python
    check_docker
    check_git

    echo ""
    if [ -f "$SCRIPT_DIR/pyproject.toml" ] && [ -d "$SCRIPT_DIR/tschan" ]; then
        INSTALL_DIR="${TSCHAN_INSTALL_DIR:-$SCRIPT_DIR}"
        info "Installing tschan from local checkout: ${INSTALL_DIR}"
        cd "$INSTALL_DIR"
    else
        INSTALL_DIR="${TSCHAN_INSTALL_DIR:-$HOME/.tschan}"
        info "Installing tschan to ${INSTALL_DIR}..."
    fi

    if [ "$INSTALL_DIR" != "$SCRIPT_DIR" ] && [ -d "$INSTALL_DIR" ]; then
        info "Updating existing installation..."
        cd "$INSTALL_DIR"
        git pull --ff-only || die "Failed to update. Try removing $INSTALL_DIR and re-running."
    elif [ "$INSTALL_DIR" != "$SCRIPT_DIR" ]; then
        git clone "$REPO_URL" "$INSTALL_DIR" || die "Failed to clone repository."
        cd "$INSTALL_DIR"
    fi

    info "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv || die "Failed to create virtual environment. Ensure 'python3-venv' is installed (e.g., sudo apt install python3-venv)."

    info "Installing Python package..."
    install_python_package

    # Verify installation
    if [ -f "./.venv/bin/tschan" ]; then
        local bin_dir="$HOME/.local/bin"
        mkdir -p "$bin_dir"
        ln -sf "$INSTALL_DIR/.venv/bin/tschan" "$bin_dir/tschan"
        
        if command -v tschan &>/dev/null; then
            ok "tschan installed successfully!"
        else
            echo ""
            echo -e "${PINK}${BOLD}Almost there!${NC} Add this to your shell profile (~/.bashrc or ~/.zshrc):"
            echo ""
            echo -e "  export PATH=\"$bin_dir:\$PATH\""
            echo ""
            ok "tschan installed to $bin_dir/tschan"
        fi
    else
        die "Installation completed but 'tschan' command not found."
    fi

    echo ""
    echo -e "${PINK}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  Quick Start:${NC}"
    echo ""
    echo "  1. Run the setup wizard:"
    echo -e "     ${CYAN}tschan --setup${NC}"
    echo ""
    echo "  2. tschan creates and manages your project at:"
    echo -e "     ${CYAN}\$HOME/tschan-server${NC}"
    echo ""
    echo "  3. After setup, open the management panel from anywhere:"
    echo -e "     ${CYAN}tschan${NC}"
    echo -e "${PINK}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

do_install
