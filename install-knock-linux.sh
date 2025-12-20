#!/bin/bash

# Install wget if not already installed
if ! command -v wget &> /dev/null; then
    echo "Installing wget..."
    sudo apt-get update
    sudo apt-get install -y wget
fi

# Download knock.py using wget
echo "Downloading knock.py..."
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knock.py -O /usr/local/bin/knock

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-tk python3-pip

# Copy files to the appropriate locations
echo "Copying files..."
cp knock.py /usr/local/bin/knock
cp knock.desktop /usr/share/applications/

# Make the script executable
chmod +x /usr/local/bin/knock

# Add to autostart for all desktop environments
echo "Adding to autostart..."
mkdir -p ~/.config/autostart
cp knock.desktop ~/.config/autostart/

# Additional autostart directories for other desktop environments
mkdir -p ~/.kde/Autostart
cp knock.desktop ~/.kde/Autostart/

mkdir -p ~/.config/xfce4/autostart
cp knock.desktop ~/.config/xfce4/autostart/

mkdir -p ~/.config/mate/autostart
cp knock.desktop ~/.config/mate/autostart/

mkdir -p ~/.config/cinnamon/autostart
cp knock.desktop ~/.config/cinnamon/autostart/

echo "Installation completed successfully."