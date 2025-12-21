#!/bin/bash

echo "=========================================="
echo "Knocking Goose Installer v3.2"
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

# Test if kg works
echo "Testing installation..."
if /usr/bin/kg --version &> /dev/null; then
    echo "✓ Knocking Goose installed successfully"
else
    echo "✗ Installation test failed"
    exit 1
fi

# Create autostart script wrapper
echo "Creating autostart wrapper..."
AUTOSTART_SCRIPT="/usr/local/bin/kg-autostart"
sudo tee "$AUTOSTART_SCRIPT" > /dev/null << 'EOFSCRIPT'
#!/bin/bash
# Wait for desktop to be ready
sleep 5
# Start Knocking Goose
/usr/bin/kg -default > /tmp/kg.log 2>&1 &
EOFSCRIPT

sudo chmod +x "$AUTOSTART_SCRIPT"

# Create .desktop file for autostart
echo "Creating autostart entry..."
DESKTOP_FILE="$HOME/.config/autostart/knocking-goose.desktop"
mkdir -p "$HOME/.config/autostart"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Knocking Goose
Comment=USB Device Sound Notifier - Monitors USB connections
Exec=/usr/local/bin/kg-autostart
Icon=/usr/share/icons/knocking-goose-icon.png
Terminal=false
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
X-KDE-autostart-after=panel
X-MATE-Autostart-enabled=true
StartupNotify=false
Categories=Utility;System;
EOF

chmod +x "$DESKTOP_FILE"
echo "Autostart entry created at: $DESKTOP_FILE"

# Systemd user service (better method)
echo "Creating systemd user service..."
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

cat > "$SYSTEMD_DIR/knocking-goose.service" << 'EOF'
[Unit]
Description=Knocking Goose USB Sound Notifier
After=graphical-session.target sound.target

[Service]
Type=simple
ExecStart=/usr/bin/kg -default
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# Reload and enable systemd service
systemctl --user daemon-reload
systemctl --user enable knocking-goose.service

# Start it now
echo "Starting Knocking Goose service..."
systemctl --user start knocking-goose.service

# Check if it's running
sleep 2
if systemctl --user is-active --quiet knocking-goose.service; then
    echo "✓ Knocking Goose is now running!"
else
    echo "⚠ Service might need manual start. Run: systemctl --user start knocking-goose.service"
fi

# Cleanup downloaded files
echo "Cleaning up..."
rm -f knocking-goose.py knocking-goose-icon.png

echo ""
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo ""
echo "Knocking Goose v3.2 has been installed!"
echo ""
echo "Status:"
systemctl --user status knocking-goose.service --no-pager -l
echo ""
echo "Quick Commands:"
echo "  kg list               - List connected USB devices"
echo "  kg history            - Show connection history"
echo "  kg stats              - Show statistics"
echo "  kg --version          - Show version"
echo "  kg --man              - Show manual"
echo ""
echo "Service Commands:"
echo "  systemctl --user status knocking-goose.service"
echo "  systemctl --user stop knocking-goose.service"
echo "  systemctl --user restart knocking-goose.service"
echo ""
echo "Knocking Goose is running and will auto-start on login!"
echo "=========================================="
