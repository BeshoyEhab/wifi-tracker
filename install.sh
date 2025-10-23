#!/bin/bash

# WiFi Tracker Installation Script

echo "Installing WiFi Tracker..."

# Detect shell
if [ -n "$ZSH_VERSION" ]; then
    SHELL_NAME="zsh"
    CONFIG_FILE="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_NAME="bash"
    CONFIG_FILE="$HOME/.bashrc"
elif [ -n "$FISH_VERSION" ]; then
    SHELL_NAME="fish"
    CONFIG_FILE="$HOME/.config/fish/config.fish"
else
    echo "Unsupported shell. Please use bash or zsh."
    exit 1
fi

echo "Detected shell: $SHELL_NAME"

# Make script executable
chmod +x wifi-tracker

# Create bin directory if it doesn't exist
mkdir -p ~/.local/share/bin

# Copy script and modules to bin directory
cp wifi-tracker ~/.local/share/bin/
cp -r wifi_tracker_modules ~/.local/share/bin/

# Check if PATH already includes ~/.local/share/bin
if ! echo "$PATH" | grep -q "$HOME/.local/share/bin"; then
  if [ "$SHELL_NAME" = "fish" ]; then
      echo "Adding ~/.local/share/bin to PATH in $CONFIG_FILE"
      echo 'fish_add_path $HOME/.local/share/bin' >> "$CONFIG_FILE"
      echo "Please run 'source $CONFIG_FILE' or restart your terminal to apply changes."
      exit 0
  else
    echo "Adding ~/.local/share/bin to PATH in $CONFIG_FILE"
    echo 'export PATH="$HOME/.local/share/bin:$PATH"' >> "$CONFIG_FILE"
    echo "Please run 'source $CONFIG_FILE' or restart your terminal to apply changes."
  fi
else
    echo "~/.local/share/bin is already in PATH."
fi

echo "Installation complete! You can now run 'wifi-tracker' from anywhere."
