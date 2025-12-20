# Knocking Goose - USB Device Sound Notifier

Knocking Goose is a Python tool that runs in the background and plays a sound when a USB device is connected or disconnected. It allows you to customize sounds for general USB devices and specific USB devices.

## Features

- Runs in the background without an open window.
- Plays a sound when a USB device is connected or disconnected.
- Customizable sounds for general USB devices.
- Customizable sounds for specific USB devices (one for connect and one for disconnect).
- Graphical interface with Dark and Light mode support.
- Terminal interface with commands to list all functions and commands.
- Auto-start functionality.

## Installation

### Linux

1. Download the installation script:
   ```bash
   wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/install-knocking-goose-linux.sh -O install-knocking-goose-linux.sh
   ```

2. Make the script executable:
   ```bash
   chmod +x install-knocking-goose-linux.sh
   ```

3. Run the installation script:
   ```bash
   sudo ./install-knocking-goose-linux.sh
   ```

### Windows

1. Run the installation script:
   ```bat
   install-knocking-goose-windows.bat
   ```

## Usage

### Graphical Interface

Start the graphical interface by running:
```bash
cd /usr/local/bin/
python3 knocking-goose-gui.py
```

### Terminal Interface

Use the following commands:
```bash
kg --help
kg --man
```

## Configuration

The configuration is stored in `kg_config.json`. You can edit this file manually or use the graphical interface to change the settings.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.