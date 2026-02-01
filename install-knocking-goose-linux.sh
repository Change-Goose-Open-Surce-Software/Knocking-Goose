#!/bin/bash

apt update
apt install -y -qq python3 python3-gi python3-pyudev gir1.2-gstreamer-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly wget

wget -q https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/knocking-goose.py -O /usr/bin/kg
wget -q https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/knocking-goose-icon.png -O /usr/share/icons/knocking-goose-icon.png

chmod +x /usr/bin/kg

mkdir -p /usr/share/knocking-goose/sounds
wget -q https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/Start.mp3 -O /usr/share/knocking-goose/sounds/Start.mp3 2>/dev/null || true
wget -q https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/Off.mp3 -O /usr/share/knocking-goose/sounds/Off.mp3 2>/dev/null || true
wget -q https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main/Quack.mp3 -O /usr/share/knocking-goose/sounds/Quack.mp3 2>/dev/null || true

mkdir -p /etc/xdg/autostart
cat > /etc/xdg/autostart/knocking-goose.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Knocking Goose
Exec=/usr/bin/kg -default
Icon=/usr/share/icons/knocking-goose-icon.png
Terminal=false
X-GNOME-Autostart-enabled=true
Categories=Utility;
EOF

kg
