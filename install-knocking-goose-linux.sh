#!/bin/bash

echo "=========================================="
echo "Knocking Goose Installer v4.0"
echo "=========================================="

# Install wget if not already installed
if ! command -v wget &> /dev/null; then
    echo "Installing wget..."
    sudo apt-get update
    sudo apt-get install -y wget
fi

# Download files using wget
echo "Downloading files..."
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/knocking-goose.py -O knocking-goose.py
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/knocking-goose-icon.png -O knocking-goose-icon.png
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/kg_start.sh -O kg_start.sh
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/kg_start.desktop -O kg_start.desktop

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
sudo cp kg_start.sh /usr/bin/kg_start.sh
sudo cp kg_start.desktop /etc/xdg/autostart/kg_start.desktop

# Make scripts executable
sudo chmod +x /usr/bin/kg
sudo chmod +x /usr/bin/kg_start.sh

# Test if kg works
echo "Testing installation..."
if /usr/bin/kg --version &> /dev/null; then
    echo "✓ Knocking Goose installed successfully"
else
    echo "✗ Installation test failed"
    exit 1
fi

# Execute the first two commands from kg_start.sh to set up the updater
echo "Setting up auto-updater..."
sudo wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/install-knocking-goose-linux.sh -O /usr/bin/kg_install-knocking-goose-linux.sh
sudo chmod +x /usr/bin/kg_install-knocking-goose-linux.sh
echo "✓ Auto-updater configured"

# Start Knocking Goose now for current user
echo "Starting Knocking Goose for current user..."
kg -default > /tmp/kg.log 2>&1 &
sleep 2

# Check if it's running
if pgrep -f "kg -default" > /dev/null; then
    echo "✓ Knocking Goose is now running!"
else
    echo "⚠ Could not start automatically. Run manually: kg -default &"
fi

# Cleanup downloaded files
echo "Cleaning up..."
rm -f knocking-goose.py knocking-goose-icon.png kg_start.sh kg_start.desktop

echo ""
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo ""
echo "Knocking Goose v4.0 has been installed!"
echo ""
echo "✓ System-wide autostart configured at: /etc/xdg/autostart/kg_start.desktop"
echo "✓ Startup script at: /usr/bin/kg_start.sh"
echo "✓ Auto-updater at: /usr/bin/kg_install-knocking-goose-linux.sh"
echo ""
echo "Knocking Goose will automatically start for ALL users on login!"
echo ""
echo "Quick Commands:"
echo "  kg list               - List connected USB devices"
echo "  kg history            - Show connection history"
echo "  kg stats              - Show statistics"
echo "  kg colour device red  - Set device color"
echo "  kg colours            - Show all colors"
echo "  kg --version          - Show version"
echo ""
echo "Current Status:"
pgrep -f "kg -default" > /dev/null && echo "  ✓ Running" || echo "  ⚠ Not running (will start on next login)"
echo ""
echo "=========================================="
