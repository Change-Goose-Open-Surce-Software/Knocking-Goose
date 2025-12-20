#!/bin/bash

# Install wget or curl if not already installed
if ! command -v wget &> /dev/null && ! command -v curl &> /dev/null; then
    echo "Installing wget or curl..."
    sudo apt-get update
    sudo apt-get install -y wget
fi

# Download knock.py using wget or curl
echo "Downloading knock.py..."
if command -v wget &> /dev/null; then
    wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knock.py -O /usr/local/bin/knock
elif command -v curl &> /dev/null; then
    curl -o /usr/local/bin/knock https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knock.py
else
    echo "Neither wget nor curl is available. Please install one of them manually."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-tk python3-pip

# Install Python packages
echo "Installing Python packages..."
pip3 install playsound pyudev

# Copy files to the appropriate locations
echo "Copying files..."
cp knock.py /usr/local/bin/knock
cp knock.desktop /usr/share/applications/

# Make the script executable
chmod +x /usr/local/bin/knock

# Add to autostart
echo "Adding to autostart..."
mkdir -p ~/.config/autostart
cp knock.desktop ~/.config/autostart/

echo "Installation completed successfully."