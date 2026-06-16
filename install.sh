#!/usr/bin/env bash
# WiFi Tracker - Install/Update script
# Usage: ./install.sh
#
# This installs wifi-tracker as a proper Python package using uv/pipx/pip
# and sets up shell completions for bash, zsh, and fish.
# To update, just run this script again.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="wifi-tracker"

# Check if uv is available, fallback to pipx, then pip
install_package() {
    if command -v uv &>/dev/null; then
        echo "Installing with uv..."
        uv tool install "$SCRIPT_DIR" --force
    elif command -v pipx &>/dev/null; then
        echo "Installing with pipx..."
        pipx install "$SCRIPT_DIR" --force
    elif command -v pip &>/dev/null; then
        echo "Installing with pip (user)..."
        pip install --user --force-reinstall "$SCRIPT_DIR"
    else
        echo "Error: No installer found. Install uv, pipx, or pip first."
        exit 1
    fi
}

install_completions() {
    echo "Installing shell completions..."

    # Bash completions
    local bash_dir="$HOME/.local/share/bash-completion/completions"
    mkdir -p "$bash_dir"
    cp "$SCRIPT_DIR/completions/wifi-tracker.bash" "$bash_dir/wifi-tracker"
    echo "  Bash: $bash_dir/wifi-tracker"

    # Zsh completions
    local zsh_dir="$HOME/.local/share/zsh/site-functions"
    mkdir -p "$zsh_dir"
    cp "$SCRIPT_DIR/completions/_wifi-tracker" "$zsh_dir/_wifi-tracker"
    echo "  Zsh:  $zsh_dir/_wifi-tracker"

    # Fish completions
    local fish_dir="$HOME/.config/fish/completions"
    mkdir -p "$fish_dir"
    cp "$SCRIPT_DIR/completions/wifi-tracker.fish" "$fish_dir/wifi-tracker.fish"
    echo "  Fish: $fish_dir/wifi-tracker.fish"
}

uninstall_old() {
    # Remove old manual installation
    local old_paths=(
        "$HOME/.local/share/bin/$APP_NAME"
        "$HOME/.local/share/bin/wifi_tracker_modules"
        "$HOME/.config/fish/bin/$APP_NAME"
        "$HOME/.config/fish/bin/wifi_tracker_modules"
    )

    for path in "${old_paths[@]}"; do
        if [ -e "$path" ]; then
            echo "Removing old: $path"
            rm -rf "$path"
        fi
    done
}

echo "=== WiFi Tracker Installer ==="
echo ""

# Uninstall old manual copies
uninstall_old

# Install/update the package
install_package

# Install shell completions
install_completions

echo ""
echo "=== Done ==="
echo "Run: wifi-tracker --help"
echo "Data: ~/.local/share/wifi-tracker/"
echo "Logs: ~/.cache/wifi-tracker/"
echo ""
echo "Note: Restart your shell or run 'source ~/.bashrc' for completions to take effect."
