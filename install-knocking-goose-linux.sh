#!/bin/bash

echo "=========================================="
echo "Knocking Goose Installer v3.1"
echo "=========================================="

# Install wget if not already installed
if ! command -v wget &> /dev/null; then
    echo "Installing wget..."
    sudo apt-get update
    sudo apt-get install -y wget
fi

# Download files using wget
echo "Downloading files..."
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knocking-goose.py -O knocking-goose.py
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knocking-goose-icon.png -O knocking-goose-icon.png

# Install dependencies using apt only
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-tk \
    python3-gi \
    python3-pyudev \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-tools

# Copy files to the appropriate locations
echo "Copying files..."
sudo cp knocking-goose.py /usr/bin/kg
sudo cp knocking-goose-icon.png /usr/share/icons/knocking-goose-icon.png

# Make the script executable
sudo chmod +x /usr/bin/kg

# Create .desktop file for autostart
echo "Creating autostart entry..."
DESKTOP_FILE="$HOME/.config/autostart/knocking-goose.desktop"
mkdir -p "$HOME/.config/autostart"

cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Type=Application
Name=Knocking Goose
Comment=USB Device Sound Notifier - Monitors USB connections
Exec=kg -default
Icon=/usr/share/icons/knocking-goose-icon.png
Terminal=false
Categories=Utility;System;
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
X-MATE-Autostart-enabled=true
EOF

echo "Autostart entry created at: $DESKTOP_FILE"

# Additional autostart methods for different desktop environments

# KDE Plasma (older versions)
if [ -d "$HOME/.kde/Autostart" ] || [ -d "$HOME/.kde4/Autostart" ]; then
    echo "Detected KDE, creating additional autostart entry..."
    mkdir -p "$HOME/.kde/Autostart"
    cp "$DESKTOP_FILE" "$HOME/.kde/Autostart/"
    mkdir -p "$HOME/.kde4/Autostart"
    cp "$DESKTOP_FILE" "$HOME/.kde4/Autostart/"
fi

# XFCE (additional location)
if [ -d "$HOME/.config/xfce4" ]; then
    echo "Detected XFCE, creating additional autostart entry..."
    mkdir -p "$HOME/.config/xfce4/autostart"
    cp "$DESKTOP_FILE" "$HOME/.config/xfce4/autostart/"
fi

# LXDE/LXQt
if [ -d "$HOME/.config/lxsession" ] || command -v lxsession &> /dev/null; then
    echo "Detected LXDE/LXQt, creating additional autostart entry..."
    mkdir -p "$HOME/.config/lxsession/LXDE/autostart"
    echo "@kg -default" >> "$HOME/.config/lxsession/LXDE/autostart"
fi

# Cinnamon (additional location)
if command -v cinnamon &> /dev/null; then
    echo "Detected Cinnamon, verifying autostart entry..."
    mkdir -p "$HOME/.config/cinnamon/autostart"
    cp "$DESKTOP_FILE" "$HOME/.config/cinnamon/autostart/"
fi

# Mate (additional location)
if command -v mate-session &> /dev/null; then
    echo "Detected MATE, verifying autostart entry..."
    mkdir -p "$HOME/.config/mate/autostart"
    cp "$DESKTOP_FILE" "$HOME/.config/mate/autostart/"
fi

# Budgie
if command -v budgie-desktop &> /dev/null; then
    echo "Detected Budgie, autostart via XDG autostart..."
    # Uses standard XDG autostart, already created
fi

# Deepin
if command -v startdde &> /dev/null; then
    echo "Detected Deepin, autostart via XDG autostart..."
    # Uses standard XDG autostart, already created
fi

# Pantheon (elementary OS)
if command -v pantheon-greeter &> /dev/null; then
    echo "Detected Pantheon (elementary OS), autostart via XDG autostart..."
    # Uses standard XDG autostart, already created
fi

# i3 / Sway (tiling window managers)
if command -v i3 &> /dev/null; then
    echo "Detected i3 window manager..."
    if [ -f "$HOME/.config/i3/config" ]; then
        if ! grep -q "exec.*kg" "$HOME/.config/i3/config"; then
            echo "exec --no-startup-id kg -default" >> "$HOME/.config/i3/config"
            echo "Added to i3 config. Reload i3 to apply (Mod+Shift+R)"
        fi
    fi
fi

if command -v sway &> /dev/null; then
    echo "Detected Sway window manager..."
    if [ -f "$HOME/.config/sway/config" ]; then
        if ! grep -q "exec.*kg" "$HOME/.config/sway/config"; then
            echo "exec kg -default" >> "$HOME/.config/sway/config"
            echo "Added to Sway config. Reload Sway to apply (Mod+Shift+C)"
        fi
    fi
fi

# Openbox
if command -v openbox &> /dev/null; then
    echo "Detected Openbox..."
    AUTOSTART_FILE="$HOME/.config/openbox/autostart"
    if [ -f "$AUTOSTART_FILE" ]; then
        if ! grep -q "kg" "$AUTOSTART_FILE"; then
            echo "kg -default &" >> "$AUTOSTART_FILE"
            echo "Added to Openbox autostart"
        fi
    fi
fi

# Awesome WM
if command -v awesome &> /dev/null; then
    echo "Detected Awesome WM..."
    RC_FILE="$HOME/.config/awesome/rc.lua"
    if [ -f "$RC_FILE" ]; then
        if ! grep -q "kg" "$RC_FILE"; then
            echo 'Note: Add this line to your rc.lua: awful.spawn.with_shell("kg -default")'
        fi
    fi
fi

# Systemd user service (universal fallback)
echo "Creating systemd user service..."
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

cat > "$SYSTEMD_DIR/knocking-goose.service" << 'EOF'
[Unit]
Description=Knocking Goose USB Sound Notifier
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/kg -default
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Enable systemd service
systemctl --user daemon-reload
systemctl --user enable knocking-goose.service
echo "Systemd user service created and enabled"

# Cleanup downloaded files
echo "Cleaning up..."
rm -f knocking-goose.py knocking-goose-icon.png

echo ""
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo ""
echo "Knocking Goose has been installed to: /usr/bin/kg"
echo "Autostart has been configured for your desktop environment"
echo ""
echo "Quick Start:"
echo "  kg                    - Start monitoring (will auto-start on next login)"
echo "  kg --version          - Show version"
echo "  kg --man              - Show manual"
echo "  kg list               - List connected USB devices"
echo ""
echo "To start Knocking Goose now:"
echo "  kg -default &"
echo ""
echo "Knocking Goose will automatically start on your next login!"
echo "=========================================="
