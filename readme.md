# 🪿 Knocking Goose - USB Device Sound Notifier

**The most feature-rich, open-source USB notification tool for Linux**

Knocking Goose monitors USB device connections and plays customizable sounds when devices are connected or disconnected. With support for vendor-specific sounds, device colors, statistics tracking, and script automation, it's the ultimate USB management tool for power users.

---

## ✨ Features

### Core Features
- 🔊 **Custom Sounds** - Set unique sounds for each device or vendor
- 🎨 **Color Coding** - Visual device identification with 20+ colors
- 📊 **Statistics & History** - Track all USB connections with timestamps
- 🤖 **Script Automation** - Execute custom scripts on device connect
- 🔇 **Volume Control** - Adjust notification volume (0-100%)
- 🚫 **Blacklist** - Ignore specific devices
- 🎯 **Vendor Support** - Configure all devices from same manufacturer at once
- 🐛 **Debug Mode** - Detailed USB event logging

### Advanced Features
- ⚡ **System-wide Autostart** - Works for ALL users automatically
- 🎭 **Filter Options** - Hide connects, disconnects, or default devices
- 📝 **Comprehensive Logging** - 1000 most recent events saved
- 🧪 **Sound Testing** - Test sounds without connecting devices
- 🔍 **Device Discovery** - List all connected USB devices with details

---

## 📥 Installation

### Linux (Debian/Ubuntu/Kali)

```bash
# Download installer
wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knock/main/install-knocking-goose-linux.sh

# Make executable
chmod +x install-knocking-goose-linux.sh

# Run installer (requires sudo)
sudo ./install-knocking-goose-linux.sh
```

**That's it!** Knocking Goose will:
- ✅ Install all dependencies via apt
- ✅ Set up system-wide autostart
- ✅ Start monitoring immediately
- ✅ Configure auto-updater

---

## 🚀 Quick Start

```bash
# List connected USB devices
kg list

# Set a disconnect sound (! means disconnect)
kg change-sound ! /usr/share/sounds/freedesktop/stereo/device-removed.oga

# Set sound for specific device
kg change-sound 8BitDo_IDLE_E417D8022CA9 /path/to/gamepad-sound.mp3

# Set sound for all devices from vendor (e.g., all Razer devices)
kg change-sound vendor:1532 /path/to/razer-sound.mp3

# Set device color for visual identification
kg colour default red
kg colour vendor:1532 gray

# View all available colors
kg colours

# Set volume
kg volume 50

# View connection history
kg history
kg history 7  # Last 7 days

# View statistics
kg stats

# Run script when device connects
kg action 8BitDo_IDLE /home/user/start-gaming.sh
```

---

## 📖 All Commands

### Sound Management
```bash
kg change-sound DEVICE /path/to/sound.mp3     # Set connect sound
kg change-sound vendor:XXXX /path/sound.mp3   # Set vendor sound
kg change-sound ! /path/to/sound.mp3          # Set disconnect sound (! = disconnect)
kg test-sound DEVICE                          # Test without connecting
kg test-sound !                               # Test disconnect sound
kg remove sound DEVICE                        # Remove sound
kg volume 0-100                               # Set volume
```

### Color Management
```bash
kg colour DEVICE COLOR                        # Set device color
kg colour vendor:XXXX COLOR                   # Set vendor color
kg colours                                    # Show all colors
kg remove colour DEVICE                       # Remove color
```

**Available Colors:**
black, red, green, yellow, blue, magenta, cyan, white, gray/grey, bright_red, bright_green, bright_yellow, bright_blue, bright_magenta, bright_cyan, bright_white, orange, purple, pink, lime

### Automation
```bash
kg action DEVICE /path/to/script.sh           # Execute script on connect
kg remove action DEVICE                       # Remove action
```

### Device Management
```bash
kg list                                       # List connected devices
kg blacklist DEVICE                           # Add to blacklist
kg blacklist --remove DEVICE                  # Remove from blacklist
```

### History & Statistics
```bash
kg history                                    # Last 24 hours
kg history 7                                  # Last 7 days
kg stats                                      # Connection statistics
```

### Monitoring
```bash
kg                                            # Start monitoring
kg -default                                   # Hide 'default' devices
kg -d                                         # Hide disconnects
kg -c                                         # Hide connects
kg -device                                    # Show only 'default' devices
kg -all                                       # Show duplicate events
kg --debug                                    # Debug mode
```

### Information
```bash
kg --help                                     # Show help
kg --man                                      # Show manual
kg --version                                  # Show version & changelog
```

---

## 🎯 Use Cases

### Gaming Setup
```bash
# Set distinct sounds for gaming peripherals
kg change-sound vendor:2dc8 ~/sounds/8bitdo-connect.mp3     # 8BitDo controllers
kg change-sound vendor:1532 ~/sounds/razer-connect.mp3      # Razer devices
kg colour vendor:2dc8 lime
kg colour vendor:1532 green

# Auto-start gaming software
kg action 8BitDo_IDLE_E417 ~/.scripts/start-steam.sh
```

### Professional Use
```bash
# Silent operation during work hours (via cron)
0 9 * * 1-5 kg volume 0    # Mute at 9 AM weekdays
0 17 * * 1-5 kg volume 100 # Unmute at 5 PM

# Track USB usage for security
kg history 30 > usb-audit-$(date +%F).txt
```

### System Administration
```bash
# Monitor all USB events with colors
kg colour vendor:8087 blue      # Intel devices
kg colour vendor:0781 orange    # SanDisk
kg list                         # Quick overview

# Log everything
kg --debug > /var/log/usb-events.log &
```

---

## 🆚 Comparison with Competition

| Feature | Knocking Goose | USBAlert | USB Safely Remove | udev Rules | usb-device-notifier |
|---------|---------------|----------|-------------------|------------|---------------------|
| **Platform** | ✅ Linux | ❌ Windows | ❌ Windows | ✅ Linux | ✅ Linux |
| **Price** | ✅ Free | ❌ $15 | ❌ $20 | ✅ Free | ✅ Free |
| **Custom Sounds** | ✅✅✅ | ✅ | ✅ | ❌ | ❌ |
| **Per-Device Sounds** | ✅ | ❌ | ❌ | ✅ Complex | ❌ |
| **Per-Vendor Sounds** | ✅ | ❌ | ❌ | ✅ Complex | ❌ |
| **Color Coding** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Actions/Scripts** | ✅ | ❌ | ❌ | ✅ Complex | ❌ |
| **History Tracking** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Statistics** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Blacklist** | ✅ | ❌ | ✅ | ✅ Complex | ❌ |
| **Volume Control** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Debug Mode** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Easy Setup** | ✅✅✅ | ✅✅ | ✅✅ | ❌ | ✅✅ |
| **CLI Interface** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Open Source** | ✅ | ❌ | ❌ | ✅ | ✅ |

### 🏆 Why Knocking Goose?

**Knocking Goose is the most feature-rich USB notification tool for Linux:**
- ✅ Only tool with vendor-specific sound support
- ✅ Only tool with color-coded visual feedback
- ✅ Only tool with history & statistics tracking
- ✅ Easier than udev rules, more powerful than GUI tools
- ✅ 100% Free and Open Source
- ✅ Active development and community support

---

## 📁 Configuration

Configuration is stored in `~/.config/kg_config.json`

### Example Configuration
```json
{
  "disconnect_sound": "/usr/share/sounds/freedesktop/stereo/device-removed.oga",
  "device_connect_sounds": {
    "8BitDo_IDLE_E417D8022CA9": "/home/user/sounds/gamepad.mp3"
  },
  "vendor_connect_sounds": {
    "1532": "/home/user/sounds/razer.mp3",
    "2dc8": "/home/user/sounds/8bitdo.mp3"
  },
  "device_colors": {
    "default": "red"
  },
  "vendor_colors": {
    "1532": "gray",
    "2dc8": "white"
  },
  "device_actions": {
    "8BitDo_IDLE_E417D8022CA9": "/home/user/.scripts/gaming.sh"
  },
  "volume": 75,
  "blacklist": ["default"],
  "history": []
}
```

---

## 🔧 Autostart

Knocking Goose automatically starts for **ALL users** system-wide via:
- `/etc/xdg/autostart/kg_start.desktop` (XDG autostart)
- `/usr/bin/kg_start.sh` (startup script)

### Manual Control
```bash
# Check if running
pgrep -f "kg -default"

# Start manually
kg -default &

# Stop
pkill -f "kg -default"
```

---

## 🐛 Troubleshooting

### Knocking Goose not starting automatically?
```bash
# Check autostart file
ls -la /etc/xdg/autostart/kg_start.desktop

# Check startup script
ls -la /usr/bin/kg_start.sh

# Test manually
/usr/bin/kg_start.sh
```

### No sound playing?
```bash
# Test sound file
kg test-sound DEVICE

# Check volume
kg volume 100

# Verify GStreamer installation
gst-inspect-1.0 playbin
```

### Device not recognized?
```bash
# List all devices
kg list

# Use debug mode
kg --debug

# Check with lsusb
lsusb
```

---

## 📋 System Requirements

- **OS:** Linux (Debian, Ubuntu, Kali, or derivatives)
- **Python:** 3.6+
- **Dependencies:** 
  - python3-pyudev
  - python3-gi
  - gstreamer1.0-plugins-*
  - All installed automatically via apt

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
```bash
git clone https://github.com/Change-Goose-Open-Surce-Software/Knock.git
cd Knock
sudo cp knocking-goose.py /usr/bin/kg-dev
sudo chmod +x /usr/bin/kg-dev
kg-dev --version
```

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 👥 Author

**Change-Goose-Open-Source-Software**

---

## 🌟 Star History

If you find Knocking Goose useful, please consider giving it a ⭐ on GitHub!

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/Change-Goose-Open-Surce-Software/Knock/issues)
- **Discussions:** [GitHub Discussions](https://github.com/Change-Goose-Open-Surce-Software/Knock/discussions)

---

**🪿Knocking Goose powerded by Change Goose with help from Claude Sonnet 4.5 from Anthropic**
