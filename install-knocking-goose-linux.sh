#!/bin/bash

# Install wget if not already installed
if ! command -v wget &> /dev/null; then
    echo "Installing wget..."
    sudo apt-get update
    sudo apt-get install -y wget
fi

# Download files using wget
echo "Downloading files..."
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knocking-goose.py -O knocking-goose.py
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knocking-goose.desktop -O knocking-goose.desktop
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/knocking-goose-icon.png -O knocking-goose-icon.png

# Install dependencies
echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-tk python3-pip

# Copy files to the appropriate locations
echo "Copying files..."
sudo cp knocking-goose.py /usr/bin/kg
sudo cp knocking-goose.desktop /usr/share/applications/
sudo cp knocking-goose-icon.png /usr/share/icons/

# Make the script executable
sudo chmod +x /usr/bin/kg

# Add to autostart for GNOME
echo "Adding to autostart..."
mkdir -p ~/.config/autostart
cp knocking-goose.desktop ~/.config/autostart/

echo "Installation completed successfully."