#!/usr/bin/env python3
# knocking-goose.py v5.0
import json
import os
import sys
import argparse
import threading
import time
import subprocess
import fnmatch
from datetime import datetime, timedelta
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import pyudev

# Initialize GStreamer
Gst.init(None)

# Global variables
recent_events = []
event_lock = threading.Lock()
debug_mode = False
device_snapshot = {}  # Stores current connected devices

# Sound paths
SOUNDS_DIR = "/usr/share/knocking-goose/sounds"
SOUND_START = os.path.join(SOUNDS_DIR, "Start.mp3")
SOUND_OFF = os.path.join(SOUNDS_DIR, "Off.mp3")
SOUND_QUACK = os.path.join(SOUNDS_DIR, "Quack.mp3")

class Colors:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'
    GREY = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    ORANGE = '\033[38;5;208m'
    PURPLE = '\033[38;5;129m'
    PINK = '\033[38;5;213m'
    LIME = '\033[38;5;118m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    
    @classmethod
    def get_all_colors(cls):
        return {
            'black': cls.BLACK, 'red': cls.RED, 'green': cls.GREEN, 'yellow': cls.YELLOW,
            'blue': cls.BLUE, 'magenta': cls.MAGENTA, 'cyan': cls.CYAN, 'white': cls.WHITE,
            'gray': cls.GRAY, 'grey': cls.GREY, 'bright_red': cls.BRIGHT_RED,
            'bright_green': cls.BRIGHT_GREEN, 'bright_yellow': cls.BRIGHT_YELLOW,
            'bright_blue': cls.BRIGHT_BLUE, 'bright_magenta': cls.BRIGHT_MAGENTA,
            'bright_cyan': cls.BRIGHT_CYAN, 'bright_white': cls.BRIGHT_WHITE,
            'orange': cls.ORANGE, 'purple': cls.PURPLE, 'pink': cls.PINK, 'lime': cls.LIME
        }
    
    @classmethod
    def get_color(cls, name):
        return cls.get_all_colors().get(name.lower(), cls.WHITE)

def colorize(text, color_code):
    return f"{color_code}{text}{Colors.RESET}"

def load_config():
    config_file = os.path.expanduser('~/.config/kg_config.json')
    default_config = {
        'sound_mappings': {},  # device/vendor -> {connect: path, disconnect: path}
        'device_actions': {},
        'device_colors': {},
        'vendor_colors': {},
        'volume': 100,
        'blacklist': [],
        'history': []
    }
    
    config_dir = os.path.dirname(config_file)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                if debug_mode:
                    print(f"DEBUG: Loaded config: {json.dumps(config, indent=2)}")
        except (json.JSONDecodeError, ValueError):
            print("Warning: Config file is corrupted, creating new one...")
            config = {}
        
        for key in default_config:
            if key not in config:
                config[key] = default_config[key]
        return config
    else:
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_config(config):
    config_file = os.path.expanduser('~/.config/kg_config.json')
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)
    if debug_mode:
        print(f"DEBUG: Saved config: {json.dumps(config, indent=2)}")

def get_device_color(device_id, vendor_id, config):
    if device_id in config.get('device_colors', {}):
        return Colors.get_color(config['device_colors'][device_id])
    elif vendor_id and vendor_id in config.get('vendor_colors', {}):
        return Colors.get_color(config['vendor_colors'][vendor_id])
    return Colors.WHITE

def play_sound(sound_file, volume=100):
    if sound_file and os.path.exists(sound_file):
        try:
            if debug_mode:
                print(f"DEBUG: Playing sound: {sound_file} at volume {volume}%")
            player = Gst.ElementFactory.make("playbin", "player")
            player.set_property("uri", "file://" + os.path.abspath(sound_file))
            player.set_property("volume", volume / 100.0)
            player.set_state(Gst.State.PLAYING)
            bus = player.get_bus()
            bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
            player.set_state(Gst.State.NULL)
        except Exception as e:
            print(f"Error playing sound: {e}")
    elif debug_mode:
        print(f"DEBUG: Sound file not found or not specified: {sound_file}")

def run_action(script_path, device_id):
    if script_path and os.path.exists(script_path):
        try:
            if debug_mode:
                print(f"Running action: {script_path} for device: {device_id}")
            subprocess.Popen([script_path, device_id])
        except Exception as e:
            print(f"Error running action: {e}")

def get_vendor_id(device):
    vendor = device.get('ID_VENDOR_ID', '')
    return vendor if vendor else None

def is_duplicate_event(action, device_id, window=0.5):
    global recent_events
    current_time = time.time()
    event_key = f"{action}:{device_id}"
    with event_lock:
        recent_events = [(t, k) for t, k in recent_events if current_time - t < window]
        for _, key in recent_events:
            if key == event_key:
                return True
        recent_events.append((current_time, event_key))
        return False

def log_event(device_id, action, vendor_id=None):
    config = load_config()
    event = {'timestamp': datetime.now().isoformat(), 'device': device_id, 'action': action, 'vendor': vendor_id}
    if 'history' not in config:
        config['history'] = []
    config['history'].append(event)
    if len(config['history']) > 1000:
        config['history'] = config['history'][-1000:]
    save_config(config)

def take_device_snapshot():
    """Take snapshot of currently connected devices"""
    global device_snapshot
    context = pyudev.Context()
    snapshot = {}
    for device in context.list_devices(subsystem='usb'):
        device_id = device.get('ID_SERIAL', 'default')
        vendor_id = device.get('ID_VENDOR_ID', 'N/A')
        if device_id != 'default':
            snapshot[device_id] = vendor_id
    device_snapshot = snapshot
    if debug_mode:
        print(f"DEBUG: Device snapshot: {snapshot}")
    return snapshot

def find_disconnected_device():
    """Find which device was disconnected by comparing snapshots"""
    global device_snapshot
    new_snapshot = take_device_snapshot()
    
    for device_id, vendor_id in device_snapshot.items():
        if device_id not in new_snapshot:
            if debug_mode:
                print(f"DEBUG: Found disconnected device: {device_id} (vendor: {vendor_id})")
            return device_id, vendor_id
    
    return 'default', 'N/A'

def match_pattern(pattern, text):
    """Match pattern with wildcard support"""
    result = fnmatch.fnmatch(text, pattern)
    if debug_mode:
        print(f"DEBUG: Pattern match '{pattern}' vs '{text}' = {result}")
    return result

def find_matching_sound(device_id, vendor_id, event_type, config):
    """Find matching sound with wildcard support"""
    sound_mappings = config.get('sound_mappings', {})
    
    if debug_mode:
        print(f"DEBUG: Looking for {event_type} sound for device='{device_id}', vendor='{vendor_id}'")
        print(f"DEBUG: Available sound mappings: {json.dumps(sound_mappings, indent=2)}")
    
    # Priority: exact device match > device pattern > vendor match > vendor pattern > wildcard
    candidates = []
    
    for pattern, sounds in sound_mappings.items():
        if event_type not in sounds:
            continue
            
        if pattern.startswith('vendor:'):
            vendor_pattern = pattern.split(':', 1)[1]
            if vendor_id and match_pattern(vendor_id, vendor_pattern):
                # Calculate specificity (fewer wildcards = higher priority)
                specificity = len(vendor_pattern) - vendor_pattern.count('*')
                candidates.append((specificity, sounds[event_type]))
                if debug_mode:
                    print(f"DEBUG: Vendor pattern '{vendor_pattern}' matched with specificity {specificity}")
        elif pattern == '*':
            candidates.append((0, sounds[event_type]))
            if debug_mode:
                print(f"DEBUG: Wildcard '*' matched")
        else:
            if match_pattern(device_id, pattern):
                specificity = len(pattern) - pattern.count('*')
                candidates.append((specificity + 1000, sounds[event_type]))  # Device patterns have higher priority
                if debug_mode:
                    print(f"DEBUG: Device pattern '{pattern}' matched with specificity {specificity + 1000}")
    
    if candidates:
        candidates.sort(reverse=True, key=lambda x: x[0])
        result = candidates[0][1]
        if debug_mode:
            print(f"DEBUG: Selected sound: {result}")
        return result
    
    if debug_mode:
        print(f"DEBUG: No matching sound found")
    return None

def monitor_usb(hide_connects=False, hide_disconnects=False, hide_default=False, hide_devices=False, show_all_duplicates=False):
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('usb')
    
    # Take initial snapshot
    take_device_snapshot()
    
    def handle_device_event(action, device):
        config = load_config()
        device_id = device.get('ID_SERIAL', 'default')
        vendor_id = get_vendor_id(device)
        
        # For disconnect events, try to identify the device
        if action == 'remove' and device_id == 'default':
            device_id, vendor_id = find_disconnected_device()
        
        if debug_mode:
            print(f"DEBUG: Action={action}, Device={device_id}, Vendor={vendor_id}")
        
        if device_id in config.get('blacklist', []):
            if debug_mode:
                print(f"DEBUG: Device {device_id} is blacklisted, ignoring")
            return
        if hide_default and device_id == 'default':
            return
        if hide_devices and device_id != 'default':
            return
        if not show_all_duplicates and is_duplicate_event(action, device_id):
            if debug_mode:
                print(f"DEBUG: Duplicate event detected, ignoring")
            return
        
        color = get_device_color(device_id, vendor_id, config)
        
        if action == 'add':
            if not hide_connects:
                print(colorize(f"● USB device connected: {device_id}", color))
                if vendor_id:
                    print(colorize(f"  ├─ Vendor ID: {vendor_id}", Colors.DIM + color))
            
            log_event(device_id, 'add', vendor_id)
            take_device_snapshot()  # Update snapshot
            
            sound_file = find_matching_sound(device_id, vendor_id, 'connect', config)
            if sound_file:
                play_sound(sound_file, config.get('volume', 100))
            
            if device_id in config.get('device_actions', {}):
                run_action(config['device_actions'][device_id], device_id)
        else:
            if not hide_disconnects:
                print(colorize(f"○ USB device disconnected: {device_id}", Colors.DIM + color))
                if vendor_id and vendor_id != 'N/A':
                    print(colorize(f"  ├─ Vendor ID: {vendor_id}", Colors.DIM + color))
            
            log_event(device_id, 'remove', vendor_id)
            
            sound_file = find_matching_sound(device_id, vendor_id, 'disconnect', config)
            if sound_file:
                play_sound(sound_file, config.get('volume', 100))

    for device in iter(monitor.poll, None):
        if device.action == 'add':
            handle_device_event('add', device)
        elif device.action == 'remove':
            handle_device_event('remove', device)

def change_sound(args_list):
    """Set sound with new v5.0 syntax supporting -connect and -disconnect flags"""
    config = load_config()
    
    # Parse flags and arguments
    connect_flag = '-connect' in args_list
    disconnect_flag = '-disconnect' in args_list
    
    # Remove flags from args
    filtered_args = [arg for arg in args_list if arg not in ['-connect', '-disconnect']]
    
    if len(filtered_args) < 2:
        print("Error: change-sound requires DEVICE and /path/to/sound")
        print("Usage: kg change-sound [-connect] [-disconnect] DEVICE /path/to/sound.mp3")
        print("Flags: -connect (default), -disconnect")
        return
    
    device_name = filtered_args[0]
    sound_path = filtered_args[1]
    
    if not os.path.exists(sound_path):
        print(f"Error: Sound file not found: {sound_path}")
        return
    
    # Default to connect if no flags specified
    if not connect_flag and not disconnect_flag:
        connect_flag = True
    
    if device_name not in config['sound_mappings']:
        config['sound_mappings'][device_name] = {}
    
    if connect_flag:
        config['sound_mappings'][device_name]['connect'] = sound_path
        print(f"Connect sound for '{device_name}' set to: {sound_path}")
    
    if disconnect_flag:
        config['sound_mappings'][device_name]['disconnect'] = sound_path
        print(f"Disconnect sound for '{device_name}' set to: {sound_path}")
    
    save_config(config)

def update_knocking_goose():
    """Run update via install script"""
    print(colorize("Updating Knocking Goose...", Colors.BRIGHT_CYAN))
    try:
        result = subprocess.run(['sudo', '/usr/bin/kg_install-knocking-goose-linux.sh'], check=True, capture_output=True, text=True)
        print(result.stdout)
        print(colorize("✓ Update completed successfully!", Colors.BRIGHT_GREEN))
    except subprocess.CalledProcessError as e:
        print(colorize(f"✗ Update failed: {e}", Colors.BRIGHT_RED))
        print(e.stderr)
    except FileNotFoundError:
        print(colorize("✗ Update script not found at /usr/bin/kg_install-knocking-goose-linux.sh", Colors.BRIGHT_RED))

def download_sounds():
    """Download sound files from GitHub"""
    base_url = "https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main"
    sounds = ['Start.mp3', 'Off.mp3', 'Quack.mp3']
    
    print(colorize("Downloading sound files...", Colors.BRIGHT_CYAN))
    
    # Create sounds directory
    try:
        subprocess.run(['sudo', 'mkdir', '-p', SOUNDS_DIR], check=True)
    except subprocess.CalledProcessError:
        print(colorize(f"✗ Failed to create directory {SOUNDS_DIR}", Colors.BRIGHT_RED))
        return
    
    for sound in sounds:
        url = f"{base_url}/{sound}"
        dest = os.path.join(SOUNDS_DIR, sound)
        print(f"Downloading {sound}...")
        try:
            subprocess.run(['sudo', 'wget', '-q', url, '-O', dest], check=True)
            print(colorize(f"  ✓ {sound}", Colors.BRIGHT_GREEN))
        except subprocess.CalledProcessError:
            print(colorize(f"  ✗ Failed to download {sound}", Colors.BRIGHT_RED))
    
    print(colorize("\n✓ Sound files ready!", Colors.BRIGHT_GREEN))

def easter_egg_quack():
    """Quack easter egg!"""
    print(colorize("🦆 QUACK! 🦆", Colors.BOLD + Colors.BRIGHT_YELLOW))
    
    config = load_config()
    if os.path.exists(SOUND_QUACK):
        play_sound(SOUND_QUACK, config.get('volume', 100))
    else:
        print(colorize("(Quack sound not found - run: sudo kg download-sounds)", Colors.DIM))

def set_color(device_name, color_name):
    config = load_config()
    if color_name.lower() not in Colors.get_all_colors():
        print(f"Error: Unknown color '{color_name}'")
        print("\nAvailable colors:")
        show_colors()
        return
    if device_name.startswith('vendor:'):
        vendor_id = device_name.split(':', 1)[1]
        config['vendor_colors'][vendor_id] = color_name.lower()
        print(f"Color for vendor '{vendor_id}' set to: {colorize(color_name, Colors.get_color(color_name))}")
    else:
        config['device_colors'][device_name] = color_name.lower()
        print(f"Color for '{device_name}' set to: {colorize(color_name, Colors.get_color(color_name))}")
    save_config(config)

def show_colors():
    colors = Colors.get_all_colors()
    print("\n" + "=" * 50)
    print("Available Colors")
    print("=" * 50)
    for name, code in sorted(colors.items()):
        print(f"{colorize('■ ' + name, code):<30} {colorize('Sample Text', code)}")
    print("=" * 50 + "\n")

def set_action(device_name, script_path):
    config = load_config()
    if not os.path.exists(script_path):
        print(f"Error: Script not found: {script_path}")
        return
    if not os.access(script_path, os.X_OK):
        print(f"Warning: Script is not executable: {script_path}")
        print("Run: chmod +x " + script_path)
    config['device_actions'][device_name] = script_path
    print(f"Action for '{device_name}' set to: {script_path}")
    save_config(config)

def manage_blacklist(device_name, remove=False):
    config = load_config()
    if remove:
        if device_name in config['blacklist']:
            config['blacklist'].remove(device_name)
            print(f"'{device_name}' removed from blacklist")
        else:
            print(f"'{device_name}' is not in blacklist")
    else:
        if device_name not in config['blacklist']:
            config['blacklist'].append(device_name)
            print(f"'{device_name}' added to blacklist")
        else:
            print(f"'{device_name}' is already in blacklist")
    save_config(config)

def set_volume(volume):
    config = load_config()
    try:
        vol = int(volume)
        if vol < 0 or vol > 100:
            print("Error: Volume must be between 0 and 100")
            return
        config['volume'] = vol
        save_config(config)
        print(f"Volume set to: {vol}%")
    except ValueError:
        print("Error: Volume must be a number")

def list_devices():
    context = pyudev.Context()
    config = load_config()
    print("\n" + "=" * 70)
    print(colorize("Currently connected USB devices", Colors.BOLD + Colors.BRIGHT_CYAN))
    print("=" * 70)
    device_count = 0
    for device in context.list_devices(subsystem='usb'):
        device_id = device.get('ID_SERIAL', 'default')
        vendor_id = device.get('ID_VENDOR_ID', 'N/A')
        product_id = device.get('ID_MODEL_ID', 'N/A')
        vendor_name = device.get('ID_VENDOR', 'Unknown')
        model_name = device.get('ID_MODEL', 'Unknown')
        if device_id != 'default':
            device_count += 1
            color = get_device_color(device_id, vendor_id, config)
            print(f"\n{colorize('●', color)} Device: {colorize(device_id, color)}")
            print(f"  ├─ Vendor: {vendor_name} ({colorize(vendor_id, Colors.CYAN)})")
            print(f"  └─ Model: {model_name} ({product_id})")
    print("\n" + "=" * 70)
    print(f"Total devices: {device_count}")
    print("=" * 70 + "\n")

def show_history(days=1):
    config = load_config()
    history = config.get('history', [])
    if not history:
        print("No history available")
        return
    cutoff = datetime.now() - timedelta(days=days)
    print("\n" + "=" * 80)
    print(colorize(f"USB Device History (last {days} day{'s' if days > 1 else ''})", Colors.BOLD + Colors.BRIGHT_CYAN))
    print("=" * 80)
    for event in reversed(history):
        event_time = datetime.fromisoformat(event['timestamp'])
        if event_time >= cutoff:
            time_str = event_time.strftime("%Y-%m-%d %H:%M:%S")
            device_str = event['device']
            vendor_id = event.get('vendor', 'N/A')
            color = get_device_color(device_str, vendor_id, config)
            if event['action'] == 'add':
                symbol = colorize("●", Colors.BRIGHT_GREEN)
                action_str = colorize("CONNECTED   ", Colors.BRIGHT_GREEN)
            else:
                symbol = colorize("○", Colors.DIM + Colors.RED)
                action_str = colorize("DISCONNECTED", Colors.RED)
            vendor_str = f" (Vendor: {colorize(vendor_id, Colors.CYAN)})" if vendor_id != 'N/A' else ""
            print(f"{symbol} {time_str} | {action_str} | {colorize(device_str, color)}{vendor_str}")
    print("=" * 80 + "\n")

def show_stats():
    config = load_config()
    history = config.get('history', [])
    if not history:
        print("No statistics available")
        return
    stats = {}
    vendor_map = {}
    for event in history:
        device = event['device']
        action = event['action']
        vendor = event.get('vendor', 'N/A')
        if device not in stats:
            stats[device] = {'connects': 0, 'disconnects': 0}
            vendor_map[device] = vendor
        if action == 'add':
            stats[device]['connects'] += 1
        else:
            stats[device]['disconnects'] += 1
    print("\n" + "=" * 90)
    print(colorize("USB Device Statistics", Colors.BOLD + Colors.BRIGHT_CYAN))
    print("=" * 90)
    print(f"{'Device':<40} {'Connects':<15} {'Disconnects':<15} {'Vendor':<10}")
    print("-" * 90)
    for device, counts in sorted(stats.items(), key=lambda x: x[1]['connects'], reverse=True):
        vendor_id = vendor_map.get(device, 'N/A')
        color = get_device_color(device, vendor_id, config)
        connects_str = colorize(str(counts['connects']), Colors.BRIGHT_GREEN)
        disconnects_str = colorize(str(counts['disconnects']), Colors.RED)
        vendor_str = colorize(vendor_id if vendor_id != 'N/A' else '-', Colors.CYAN)
        print(f"{colorize(device, color):<49} {connects_str:<24} {disconnects_str:<24} {vendor_str:<19}")
    print("=" * 90 + "\n")

def remove_config(config_type, device_name):
    config = load_config()
    if config_type == 'sound':
        if device_name in config.get('sound_mappings', {}):
            del config['sound_mappings'][device_name]
            print(f"Sound for '{device_name}' removed")
        else:
            print(f"No sound configured for '{device_name}'")
            return
    elif config_type == 'action':
        if device_name in config.get('device_actions', {}):
            del config['device_actions'][device_name]
            print(f"Action for '{device_name}' removed")
        else:
            print(f"No action configured for '{device_name}'")
            return
    elif config_type in ['color', 'colour']:
        if device_name.startswith('vendor:'):
            vendor_id = device_name.split(':', 1)[1]
            if vendor_id in config.get('vendor_colors', {}):
                del config['vendor_colors'][vendor_id]
                print(f"Color for vendor '{vendor_id}' removed")
            else:
                print(f"No color configured for vendor '{vendor_id}'")
                return
        else:
            if device_name in config.get('device_colors', {}):
                del config['device_colors'][device_name]
                print(f"Color for '{device_name}' removed")
            else:
                print(f"No color configured for '{device_name}'")
                return
    save_config(config)

def show_version():
    print("=" * 70)
    print(colorize("Knocking Goose - USB Device Sound Notifier", Colors.BOLD + Colors.BRIGHT_CYAN))
    print("=" * 70)
    print(f"\n{colorize('Current Version:', Colors.BOLD)} {colorize('5.0', Colors.BRIGHT_GREEN)}")
    print(f"{colorize('Release Date:', Colors.BOLD)} 2025-02-01")
    print("\n" + "=" * 70)
    print(colorize("VERSION HISTORY", Colors.BOLD + Colors.BRIGHT_YELLOW))
    print("=" * 70)
    versions = [
        {'version': '5.0', 'date': '2025-02-01', 'changes': [
            'FIXED: Autostart now works reliably',
            'FIXED: Config file is now properly read and applied',
            'FIXED: Start.mp3, Off.mp3, Quack.mp3 sounds play correctly',
            'FIXED: Wildcard matching now works properly',
            'FIXED: -connect and -disconnect parameters recognized',
            'NEW: --man shows comprehensive manual',
            'NEW: kg vs command shows comparison table',
            'IMPROVED: Easter egg shows only sound, no ASCII art',
            'IMPROVED: Better debug mode for troubleshooting']},
        {'version': '4.0', 'date': '2025-12-22 03:00', 'changes': [
            'NEW: kg update command - auto-update via kg_start.sh',
            'NEW: Wildcard support - use * in device/vendor names',
            'NEW: -connect and -disconnect flags for change-sound',
            'NEW: Startup/shutdown sounds (Start.mp3, Off.mp3)',
            'NEW: Easter egg - kg quack',
            'IMPROVED: Disconnect detection - shows real device name']},
        {'version': '4.0', 'date': '2025-12-22 02:00', 'changes': [
            'System-wide autostart for ALL users']},
        {'version': '3.2', 'date': '2025-12-22 01:00', 'changes': [
            'Added color support']},
        {'version': '3.0', 'date': '2025-12-21 23:45', 'changes': [
            'Vendor sounds, history, statistics']}
    ]
    for v in versions:
        print(f"\n{colorize('Version ' + v['version'], Colors.BOLD + Colors.BRIGHT_GREEN)} - {v['date']}")
        print("-" * 70)
        for change in v['changes']:
            print(f"  {colorize('•', Colors.BRIGHT_YELLOW)} {change}")
    print("\n" + "=" * 70)

def show_comparison():
    """Show comparison table - PLACEHOLDER FOR USER TO FILL IN"""
    print("\n" + "=" * 100)
    print(colorize("Knocking Goose vs Competition", Colors.BOLD + Colors.BRIGHT_CYAN))
    print("=" * 100)
    
    # PLACEHOLDER: User should insert comparison table here
    print("""
| Feature               | Knocking Goose | USBAlert   | USB Safely Remove | udev Rules      | usb-device-notifier |
|----------------------|----------------|------------|--------------------|------------------|---------------------|
| **Platform**         | ✅ Linux        | ❌ Windows  | ❌ Windows          | ✅ Linux          | ✅ Linux             |
| **Price**            | ✅ Free         | ❌ $15      | ❌ $20              | ✅ Free           | ✅ Free              |
| **Custom Sounds**    | ✅✅✅           | ✅         | ✅                  | ❌                | ❌                   |
| **Per-Device Sounds** | ✅             | ❌         | ❌                  | ✅ Complex        | ❌                   |
| **Per-Vendor Sounds** | ✅             | ❌         | ❌                  | ✅ Complex        | ❌                   |
| **Color Coding**     | ✅              | ❌         | ❌                  | ❌                | ❌                   |
| **Actions/Scripts**  | ✅              | ❌         | ❌                  | ✅ Complex        | ❌                   |
| **History Tracking**  | ✅              | ❌         | ✅                  | ❌                | ❌                   |
| **Statistics**       | ✅              | ❌         | ❌                  | ❌                | ❌                   |
| **Blacklist**        | ✅              | ❌         | ✅                  | ✅ Complex        | ❌                   |
| **Volume Control**   | ✅              | ❌         | ✅                  | ❌                | ❌                   |
| **Debug Mode**       | ✅              | ❌         | ❌                  | ❌                | ❌                   |
| **Easy Setup**       | ✅✅✅           | ✅✅       | ✅✅                | ❌                | ✅✅                 |
| **CLI Interface**    | ✅              | ❌         | ❌                  | ❌                | ❌                   |
| **Open Source**      | ✅              | ❌         | ❌                  | ✅                | ✅                   |

    """)
    
    print("=" * 100)
    print(colorize("\n🏆 Knocking Goose - The most feature-rich USB notification tool for Linux!", 
                   Colors.BOLD + Colors.BRIGHT_GREEN))
    print("=" * 100 + "\n")

def show_manual():
    """Show comprehensive manual"""
    manual_text = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    KNOCKING GOOSE v5.0 - MANUAL                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

TABLE OF CONTENTS
─────────────────
1. Introduction
2. Installation
3. Basic Usage
4. Sound Management
5. Color Management
6. Device Management
7. Automation
8. History & Statistics
9. Advanced Features
10. Troubleshooting
11. Examples

───────────────────────────────────────────────────────────────────────────────

1. INTRODUCTION
───────────────

Knocking Goose is a powerful USB device sound notifier for Linux that monitors
USB connections and plays customizable sounds. It supports per-device sounds,
per-vendor sounds, wildcard patterns, color coding, script automation, and more.

───────────────────────────────────────────────────────────────────────────────

2. INSTALLATION
───────────────

Quick Install (One-liner):
  wget https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/\\
  Knocking-Goose/main/install-knocking-goose-linux.sh && \\
  chmod +x install-knocking-goose-linux.sh && \\
  sudo ./install-knocking-goose-linux.sh

The installer will:
  • Install all required dependencies (Python3, GStreamer, pyudev)
  • Set up system-wide autostart for ALL users
  • Download default sounds (Start.mp3, Off.mp3, Quack.mp3)
  • Configure auto-updater
  • Start monitoring immediately

After installation:
  • Knocking Goose runs automatically on login
  • Command 'kg' is available system-wide
  • Configuration is stored in ~/.config/kg_config.json

───────────────────────────────────────────────────────────────────────────────

3. BASIC USAGE
──────────────

Starting Knocking Goose:
  kg                      # Start monitoring (plays Start.mp3)
  kg -default             # Hide 'default' devices
  kg --debug              # Enable debug mode

Stopping Knocking Goose:
  Press Ctrl+C            # Graceful shutdown (plays Off.mp3)
  pkill -f "kg -default"  # Force stop

Getting Help:
  kg --help               # Quick command reference
  kg --man                # This comprehensive manual
  kg --version            # Version info and changelog

───────────────────────────────────────────────────────────────────────────────

4. SOUND MANAGEMENT
───────────────────

Setting Sounds:
  kg change-sound DEVICE /path/to/connect.mp3
      Set connect sound for specific device
  
  kg change-sound -connect DEVICE /path/to/connect.mp3
      Explicitly set connect sound
  
  kg change-sound -disconnect DEVICE /path/to/disconnect.mp3
      Set disconnect sound
  
  kg change-sound -connect -disconnect DEVICE /path/to/sound.mp3
      Set both connect and disconnect to same sound

Wildcard Support:
  kg change-sound "8BitDo*" /sounds/gamepad.mp3
      Match all devices starting with "8BitDo"
  
  kg change-sound "*Mouse*" /sounds/mouse.mp3
      Match any device containing "Mouse"
  
  kg change-sound "vendor:153*" /sounds/razer.mp3
      Match all Razer devices (vendor ID starts with 153)

Global Sounds:
  kg change-sound -disconnect "*" /sounds/disconnect.mp3
      Set default disconnect sound for ALL devices

Testing Sounds:
  kg test-sound DEVICE              # Test connect sound
  kg test-sound -disconnect DEVICE  # Test disconnect sound

Volume Control:
  kg volume 75              # Set to 75%
  kg volume 0               # Mute
  kg volume 100             # Maximum

Download Default Sounds:
  sudo kg download-sounds   # Downloads Start.mp3, Off.mp3, Quack.mp3

Removing Sounds:
  kg remove sound DEVICE    # Remove sound configuration

───────────────────────────────────────────────────────────────────────────────

5. COLOR MANAGEMENT
───────────────────

Setting Colors:
  kg colour DEVICE red                # Set device color
  kg colour vendor:1532 gray          # Set vendor color
  kg color DEVICE bright_green        # 'color' also works

Available Colors:
  kg colours                          # Show all 20+ colors
  kg colors                           # Alternative spelling

Color List:
  black, red, green, yellow, blue, magenta, cyan, white
  gray/grey, bright_red, bright_green, bright_yellow, bright_blue
  bright_magenta, bright_cyan, bright_white
  orange, purple, pink, lime

Removing Colors:
  kg remove colour DEVICE             # Remove color
  kg remove colour vendor:1532        # Remove vendor color

───────────────────────────────────────────────────────────────────────────────

6. DEVICE MANAGEMENT
────────────────────

Listing Devices:
  kg list                   # Show all connected USB devices
                            # with vendor info, model, IDs

Blacklist (Ignore Devices):
  kg blacklist DEVICE              # Add to blacklist
  kg blacklist --remove DEVICE     # Remove from blacklist

Finding Device Names:
  1. Run: kg list
  2. Connect/disconnect your device
  3. Note the device name shown in output
  4. Use that name in commands

Example Device Names:
  • 8BitDo_IDLE_E417D8022CA9
  • SanDisk_Cruzer_Blade_4C530001234567890123
  • Logitech_USB_Receiver

Vendor IDs:
  • 1532 = Razer
  • 046d = Logitech  
  • 0781 = SanDisk
  • 2dc8 = 8BitDo
  • 8087 = Intel

───────────────────────────────────────────────────────────────────────────────

7. AUTOMATION
─────────────

Execute Scripts on Device Connect:
  kg action DEVICE /path/to/script.sh
      Run script when device connects
      Script receives device name as $1

Example Script (/home/user/start-gaming.sh):
  #!/bin/bash
  echo "Controller connected: $1"
  steam &
  discord &

Make Script Executable:
  chmod +x /home/user/start-gaming.sh

Remove Action:
  kg remove action DEVICE

───────────────────────────────────────────────────────────────────────────────

8. HISTORY & STATISTICS
────────────────────────

View History:
  kg history                # Last 24 hours
  kg history 7              # Last 7 days
  kg history 30             # Last 30 days

Shows:
  • Timestamp of each connection/disconnection
  • Device name
  • Vendor ID
  • Connection status (colored)

View Statistics:
  kg stats                  # Summary of all device activity

Shows:
  • Total connects per device
  • Total disconnects per device
  • Vendor information
  • Sorted by most active devices

History Storage:
  • Last 1000 events stored
  • Location: ~/.config/kg_config.json
  • Automatic cleanup of old events

───────────────────────────────────────────────────────────────────────────────

9. ADVANCED FEATURES
────────────────────

Monitoring Filters:
  kg -c                     # Hide connect messages
  kg -d                     # Hide disconnect messages
  kg -default               # Hide 'default' devices
  kg -device                # Show ONLY 'default' devices
  kg -all                   # Show duplicate events

Debug Mode:
  kg --debug                # Verbose logging
                            # Shows pattern matching
                            # Shows config loading
                            # Shows sound file paths

Auto-Update:
  kg update                 # Update to latest version

Easter Egg:
  kg quack                  # Play quack sound 🦆

Comparison Table:
  kg vs                     # Show feature comparison

Configuration File:
  Location: ~/.config/kg_config.json
  Format: JSON
  Can be edited manually (be careful with syntax!)

───────────────────────────────────────────────────────────────────────────────

10. TROUBLESHOOTING
───────────────────

Problem: Knocking Goose not starting on login
Solution:
  1. Check autostart file exists:
     ls -la /etc/xdg/autostart/kg_start.desktop
  
  2. Check startup script:
     ls -la /usr/bin/kg_start.sh
  
  3. Test manually:
     /usr/bin/kg_start.sh
  
  4. Reinstall:
     sudo ./install-knocking-goose-linux.sh

Problem: No sound playing
Solution:
  1. Check volume:
     kg volume 100
  
  2. Test sound file:
     kg test-sound DEVICE
  
  3. Verify sound file exists:
     ls -la /path/to/sound.mp3
  
  4. Check GStreamer:
     gst-inspect-1.0 playbin
  
  5. Enable debug mode:
     kg --debug

Problem: Device not recognized
Solution:
  1. List devices while connecting:
     kg list
  
  2. Use debug mode:
     kg --debug
  
  3. Check with lsusb:
     lsusb
  
  4. Try wildcard pattern:
     kg change-sound "*PartOfName*" /sound.mp3

Problem: Wildcards not matching
Solution:
  1. Enable debug mode to see pattern matching:
     kg --debug
  
  2. Check exact device name:
     kg list
  
  3. Use quotes around wildcards:
     kg change-sound "8BitDo*" /sound.mp3
  
  4. Test patterns carefully:
     "*" = everything
     "Device*" = starts with Device
     "*Device*" = contains Device
     "*Device" = ends with Device

Problem: Config not being read
Solution:
  1. Check config file exists:
     cat ~/.config/kg_config.json
  
  2. Validate JSON syntax:
     python3 -m json.tool ~/.config/kg_config.json
  
  3. Enable debug mode:
     kg --debug
  
  4. Delete and recreate:
     rm ~/.config/kg_config.json
     kg volume 100  # Creates new config

───────────────────────────────────────────────────────────────────────────────

11. EXAMPLES
────────────

Example 1: Gaming Setup
  # Set sounds for gaming devices
  kg change-sound "8BitDo*" ~/sounds/controller-connect.mp3
  kg change-sound -disconnect "8BitDo*" ~/sounds/controller-disconnect.mp3
  
  # Set colors
  kg colour "8BitDo*" lime
  
  # Auto-start Steam
  kg action 8BitDo_IDLE ~/.scripts/start-steam.sh
  
  # Hide non-gaming devices
  kg blacklist default

Example 2: Professional Workspace
  # Silent operation
  kg volume 0
  
  # Track all USB activity
  kg history 30 > usb-audit-$(date +%F).txt
  
  # Color-code work devices
  kg colour vendor:0781 orange    # SanDisk drives
  kg colour vendor:046d blue      # Logitech peripherals

Example 3: Security Monitoring
  # Set alert sounds for unknown devices
  kg change-sound "*" ~/sounds/alert.mp3
  
  # Color-code known devices
  kg colour "MyDevice*" green
  kg colour "vendor:1234" green
  
  # Blacklist known devices to only see alerts for new ones
  kg blacklist MyDevice1
  kg blacklist MyDevice2
  
  # Run in debug mode to log everything
  kg --debug > /var/log/usb-monitor.log &

Example 4: Multi-Device Setup
  # Different sounds per vendor
  kg change-sound vendor:1532 ~/sounds/razer.mp3    # Razer
  kg change-sound vendor:046d ~/sounds/logitech.mp3 # Logitech
  kg change-sound vendor:0781 ~/sounds/sandisk.mp3  # SanDisk
  
  # Different disconnect sound
  kg change-sound -disconnect "*" ~/sounds/generic-disconnect.mp3
  
  # Color code by vendor
  kg colour vendor:1532 green
  kg colour vendor:046d blue
  kg colour vendor:0781 orange

Example 5: Wildcard Mastery
  # Match all mouse devices
  kg change-sound "*Mouse*" ~/sounds/mouse.mp3
  kg colour "*Mouse*" cyan
  
  # Match all keyboards
  kg change-sound "*Keyboard*" ~/sounds/keyboard.mp3
  kg colour "*Keyboard*" blue
  
  # Match specific product line
  kg change-sound "Logitech_G*" ~/sounds/logitech-gaming.mp3
  
  # Match by vendor with wildcard
  kg change-sound "vendor:046*" ~/sounds/logitech-all.mp3

───────────────────────────────────────────────────────────────────────────────

QUICK REFERENCE CARD
────────────────────

Essential Commands:
  kg                              Start monitoring
  kg list                         List devices
  kg change-sound DEVICE /path    Set sound
  kg colour DEVICE COLOR          Set color
  kg history                      View history
  kg --help                       Quick help
  kg --man                        This manual

Common Patterns:
  kg change-sound -disconnect "*" /path      Global disconnect
  kg change-sound "Device*" /path            Wildcard device
  kg change-sound vendor:1532 /path          Vendor sound
  kg colour vendor:1532 green                Vendor color
  kg volume 75                               Set volume
  kg blacklist DEVICE                        Ignore device

Files & Locations:
  Config:        ~/.config/kg_config.json
  Sounds:        /usr/share/knocking-goose/sounds/
  Autostart:     /etc/xdg/autostart/kg_start.desktop
  Startup:       /usr/bin/kg_start.sh
  Executable:    /usr/bin/kg

───────────────────────────────────────────────────────────────────────────────

For more information, visit:
  https://github.com/Change-Goose-Open-Surce-Software/Knocking-Goose

Report bugs or request features:
  https://github.com/Change-Goose-Open-Surce-Software/Knocking-Goose/issues

╔══════════════════════════════════════════════════════════════════════════════╗
║                  End of Manual - Happy USB Monitoring! 🦆                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(colorize(manual_text, Colors.WHITE))

def test_sound(device_name, event_type='connect'):
    config = load_config()
    vendor_id = None
    if device_name.startswith('vendor:'):
        vendor_id = device_name.split(':', 1)[1]
        device_name = f"vendor:{vendor_id}"
    sound_file = find_matching_sound(device_name, vendor_id, event_type, config)
    if sound_file:
        print(f"Playing {event_type} sound: {sound_file}")
        play_sound(sound_file, config.get('volume', 100))
    else:
        print(f"No {event_type} sound configured for {device_name}")

def main():
    global debug_mode
    parser = argparse.ArgumentParser(
        description='Knocking Goose v5.0 - USB Device Sound Notifier',
        epilog=f"{colorize('Examples:', Colors.BOLD)}\n"
               f"  kg change-sound -connect -disconnect device /sound.mp3\n"
               f"  kg change-sound -disconnect \"*\" /sounds/disconnect.wav\n"
               f"  kg change-sound \"8BitDo*\" /sounds/gamepad.mp3\n"
               f"  kg change-sound vendor:153* /sounds/razer.mp3\n"
               f"  kg update                  # Update Knocking Goose\n"
               f"  kg quack                   # Easter egg!\n"
               f"  kg vs                      # Comparison table\n"
               f"\nFor detailed manual: kg --man",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--man', action='store_true', help='Show comprehensive manual')
    parser.add_argument('--version', action='store_true', help='Show version')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    parser.add_argument('-d', '--hide-disconnects', action='store_true')
    parser.add_argument('-c', '--hide-connects', action='store_true')
    parser.add_argument('-default', '--hide-default', action='store_true')
    parser.add_argument('-device', '--hide-devices', action='store_true')
    parser.add_argument('-all', '--show-all', action='store_true')
    parser.add_argument('command', nargs='?')
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    
    if args.debug:
        debug_mode = True
        print(colorize("DEBUG MODE ENABLED", Colors.BRIGHT_YELLOW))
    
    if args.man:
        show_manual()
        return
    
    if args.version:
        show_version()
        return
    
    if args.command == 'change-sound':
        change_sound(args.args)
    elif args.command == 'update':
        update_knocking_goose()
    elif args.command == 'quack':
        easter_egg_quack()
    elif args.command == 'vs':
        show_comparison()
    elif args.command == 'download-sounds':
        download_sounds()
    elif args.command == 'action':
        if len(args.args) < 2:
            print("Error: action requires DEVICE and /path/to/script.sh")
            sys.exit(1)
        set_action(args.args[0], args.args[1])
    elif args.command in ['colour', 'color']:
        if len(args.args) < 2:
            print("Error: colour requires DEVICE and COLOR")
            sys.exit(1)
        set_color(args.args[0], args.args[1])
    elif args.command in ['colours', 'colors']:
        show_colors()
    elif args.command == 'blacklist':
        if len(args.args) < 1:
            print("Error: blacklist requires DEVICE")
            sys.exit(1)
        remove = '--remove' in args.args
        device_name = args.args[1] if remove else args.args[0]
        manage_blacklist(device_name, remove)
    elif args.command == 'volume':
        if len(args.args) < 1:
            print("Error: volume requires NUMBER")
            sys.exit(1)
        set_volume(args.args[0])
    elif args.command == 'list':
        list_devices()
    elif args.command == 'history':
        days = int(args.args[0]) if args.args else 1
        show_history(days)
    elif args.command == 'stats':
        show_stats()
    elif args.command == 'remove':
        if len(args.args) < 2:
            print("Error: remove requires TYPE and DEVICE")
            sys.exit(1)
        remove_config(args.args[0], args.args[1])
    elif args.command == 'test-sound':
        if len(args.args) < 1:
            print("Error: test-sound requires DEVICE")
            sys.exit(1)
        disconnect_flag = '-disconnect' in args.args
        device_name = [arg for arg in args.args if arg != '-disconnect'][0]
        event_type = 'disconnect' if disconnect_flag else 'connect'
        test_sound(device_name, event_type)
    elif args.command:
        print(f"Error: Unknown command '{args.command}'")
        sys.exit(1)
    else:
        # Play startup sound
        config = load_config()
        if os.path.exists(SOUND_START):
            play_sound(SOUND_START, config.get('volume', 100))
        
        print(colorize("Starting Knocking Goose v5.0...", Colors.BRIGHT_CYAN))
        print(f"Volume: {config.get('volume', 100)}%")
        monitor_thread = threading.Thread(target=monitor_usb, args=(args.hide_connects, args.hide_disconnects, args.hide_default, args.hide_devices, args.show_all))
        monitor_thread.daemon = True
        monitor_thread.start()
        print(colorize("Knocking Goose is running!", Colors.BRIGHT_GREEN))
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(colorize("\nStopping Knocking Goose...", Colors.BRIGHT_YELLOW))
            # Play shutdown sound
            if os.path.exists(SOUND_OFF):
                play_sound(SOUND_OFF, config.get('volume', 100))

if __name__ == '__main__':
    main()
