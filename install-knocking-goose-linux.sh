#!/bin/bash

# Install wget if not already installed
if ! command -v wget &> /dev/null; then
    echo "Installing wget..."
    sudo apt-get update
    sudo apt-get install -y wget
fi

# Download knocking-goose.py using wget
echo "Downloading knocking-goose.py..."
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knocking-goose.py -O /usr/local/bin/kg

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-tk python3-pip

# Copy files to the appropriate locations
echo "Copying files..."
cp knocking-goose.py /usr/local/bin/kg
cp knocking-goose.desktop /usr/share/applications/

# Make the script executable
chmod +x /usr/local/bin/kg

# Add to autostart for all desktop environments
echo "Adding to autostart..."
mkdir -p ~/.config/autostart
cp knocking-goose.desktop ~/.config/autostart/

# Additional autostart directories for other desktop environments
mkdir -p ~/.kde/Autostart
cp knocking-goose.desktop ~/.kde/Autostart/

mkdir -p ~/.config/xfce4/autostart
cp knocking-goose.desktop ~/.config/xfce4/autostart/

mkdir -p ~/.config/mate/autostart
cp knocking-goose.desktop ~/.config/mate/autostart/

mkdir -p ~/.config/cinnamon/autostart
cp knocking-goose.desktop ~/.config/cinnamon/autostart/

echo "Installation completed successfully."