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
        'sound_mappings': {},  # New format: device/vendor -> {connect: path, disconnect: path}
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
        except (json.JSONDecodeError, ValueError):
            print("Warning: Config file is corrupted, creating new one...")
            config = {}
        
        # Migration from v4.0
        if 'disconnect_sound' in config or 'device_connect_sounds' in config:
            print("Migrating config from v4.0 to v5.0...")
            new_config = default_config.copy()
            
            # Migrate disconnect sound
            if config.get('disconnect_sound'):
                new_config['sound_mappings']['*'] = {'disconnect': config['disconnect_sound']}
            
            # Migrate device connect sounds
            for device_id, sound in config.get('device_connect_sounds', {}).items():
                if device_id not in new_config['sound_mappings']:
                    new_config['sound_mappings'][device_id] = {}
                new_config['sound_mappings'][device_id]['connect'] = sound
            
            # Migrate vendor connect sounds
            for vendor_id, sound in config.get('vendor_connect_sounds', {}).items():
                key = f"vendor:{vendor_id}"
                if key not in new_config['sound_mappings']:
                    new_config['sound_mappings'][key] = {}
                new_config['sound_mappings'][key]['connect'] = sound
            
            # Copy other settings
            for key in ['device_actions', 'device_colors', 'vendor_colors', 'volume', 'blacklist', 'history']:
                if key in config:
                    new_config[key] = config[key]
            
            with open(config_file, 'w') as f:
                json.dump(new_config, f, indent=4)
            return new_config
        
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

def get_device_color(device_id, vendor_id, config):
    if device_id in config.get('device_colors', {}):
        return Colors.get_color(config['device_colors'][device_id])
    elif vendor_id and vendor_id in config.get('vendor_colors', {}):
        return Colors.get_color(config['vendor_colors'][vendor_id])
    return Colors.WHITE

def play_sound(sound_file, volume=100):
    if sound_file and os.path.exists(sound_file):
        try:
            player = Gst.ElementFactory.make("playbin", "player")
            player.set_property("uri", "file://" + os.path.abspath(sound_file))
            player.set_property("volume", volume / 100.0)
            player.set_state(Gst.State.PLAYING)
            bus = player.get_bus()
            bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
            player.set_state(Gst.State.NULL)
        except Exception as e:
            print(f"Error playing sound: {e}")

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
    return snapshot

def find_disconnected_device():
    """Find which device was disconnected by comparing snapshots"""
    global device_snapshot
    new_snapshot = take_device_snapshot()
    
    for device_id, vendor_id in device_snapshot.items():
        if device_id not in new_snapshot:
            return device_id, vendor_id
    
    return 'default', 'N/A'

def match_pattern(pattern, text):
    """Match pattern with wildcard support"""
    return fnmatch.fnmatch(text, pattern)

def find_matching_sound(device_id, vendor_id, event_type, config):
    """Find matching sound with wildcard support"""
    sound_mappings = config.get('sound_mappings', {})
    
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
        elif pattern == '*':
            candidates.append((0, sounds[event_type]))
        else:
            if match_pattern(device_id, pattern):
                specificity = len(pattern) - pattern.count('*')
                candidates.append((specificity + 1000, sounds[event_type]))  # Device patterns have higher priority
    
    if candidates:
        candidates.sort(reverse=True, key=lambda x: x[0])
        return candidates[0][1]
    
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
            return
        if hide_default and device_id == 'default':
            return
        if hide_devices and device_id != 'default':
            return
        if not show_all_duplicates and is_duplicate_event(action, device_id):
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

def change_sound(device_name, sound_path, connect=True, disconnect=False):
    """Set sound with new v5.0 syntax"""
    config = load_config()
    
    if not os.path.exists(sound_path):
        print(f"Error: Sound file not found: {sound_path}")
        return
    
    if device_name not in config['sound_mappings']:
        config['sound_mappings'][device_name] = {}
    
    if connect:
        config['sound_mappings'][device_name]['connect'] = sound_path
        print(f"Connect sound for '{device_name}' set to: {sound_path}")
    
    if disconnect:
        config['sound_mappings'][device_name]['disconnect'] = sound_path
        print(f"Disconnect sound for '{device_name}' set to: {sound_path}")
    
    save_config(config)

def update_knocking_goose():
    """Run update via kg_start.sh"""
    print(colorize("Updating Knocking Goose...", Colors.BRIGHT_CYAN))
    try:
        result = subprocess.run(['sudo', '/usr/bin/kg_start.sh'], check=True, capture_output=True, text=True)
        print(result.stdout)
        print(colorize("✓ Update completed successfully!", Colors.BRIGHT_GREEN))
    except subprocess.CalledProcessError as e:
        print(colorize(f"✗ Update failed: {e}", Colors.BRIGHT_RED))
        print(e.stderr)
    except FileNotFoundError:
        print(colorize("✗ Update script not found at /usr/bin/kg_start.sh", Colors.BRIGHT_RED))

def download_sounds():
    """Download sound files from GitHub"""
    base_url = "https://raw.githubusercontent.com/Change-Goose-Open-Surce-Software/Knocking-Goose/main"
    sounds = ['Start.mp3', 'Off.mp3', 'Quack.mp3']
    
    print(colorize("Downloading sound files...", Colors.BRIGHT_CYAN))
    
    # Create sounds directory
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    
    for sound in sounds:
        url = f"{base_url}/{sound}"
        dest = os.path.join(SOUNDS_DIR, sound)
        print(f"Downloading {sound}...")
        try:
            subprocess.run(['wget', '-q', url, '-O', dest], check=True)
            print(colorize(f"  ✓ {sound}", Colors.BRIGHT_GREEN))
        except subprocess.CalledProcessError:
            print(colorize(f"  ✗ Failed to download {sound}", Colors.BRIGHT_RED))
    
    print(colorize("\n✓ Sound files ready!", Colors.BRIGHT_GREEN))

def easter_egg_quack():
    """Quack easter egg!"""
    print(colorize("""
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⢀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣄⡀⠀
    ⠀⠀⠀⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦
    ⠀⢀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
    ⠀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
    ⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠿⠿⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
    ⢸⣿⣿⣿⣿⣿⣿⠟⠉⠀⠀⠀⠀⠀⠀⠀⠉⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
    ⢸⣿⣿⣿⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿
    ⠈⣿⣿⣿⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃
    ⠀⠹⣿⣿⡇⠀⣀⣀⣀⠀⠀⠀⠀⠀⠀⣀⣀⣀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⠏⠀
    ⠀⠀⠹⣿⡇⠀⠿⠿⠿⠀⠀⠀⠀⠀⠀⠿⠿⠿⠀⠀⢸⣿⣿⣿⣿⣿⣿⠏⠀⠀
    ⠀⠀⠀⠹⣿⡀⠀⠀⠀⠀⢀⣀⣀⣀⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⣿⣿⠏⠀⠀⠀
    ⠀⠀⠀⠀⠘⣿⣦⣄⣀⣴⣿⣿⣿⣿⣿⣦⣀⣠⣴⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠈⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⣿⣿⣿⣿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    """, Colors.BRIGHT_YELLOW))
    print(colorize("                    🦆 QUACK! 🦆", Colors.BOLD + Colors.BRIGHT_YELLOW))
    print(colorize("         Knocking Goose says hello!", Colors.BRIGHT_CYAN))
    
    if os.path.exists(SOUND_QUACK):
        play_sound(SOUND_QUACK, 100)
    else:
        print(colorize("\n(Quack sound not found - run: sudo kg download-sounds)", Colors.DIM))

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
    print(f"{colorize('Release Date:', Colors.BOLD)} 2025-12-22 03:00")
    print("\n" + "=" * 70)
    print(colorize("VERSION HISTORY", Colors.BOLD + Colors.BRIGHT_YELLOW))
    print("=" * 70)
    versions = [
        {'version': '5.0', 'date': '2025-12-22 03:00', 'changes': [
            'NEW: kg update command - auto-update via kg_start.sh',
            'NEW: Wildcard support - use * in device/vendor names',
            'NEW: -connect and -disconnect flags for change-sound',
            'NEW: Startup/shutdown sounds (Start.mp3, Off.mp3)',
            'NEW: Easter egg - kg quack',
            'IMPROVED: Disconnect detection - shows real device name',
            'IMPROVED: Device snapshot system tracks all connections',
            'REMOVED: ! symbol - use -disconnect flag instead',
            'Migration from v4.0 config format automatic']},
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
               f"  kg change-sound -disconnect /sounds/disconnect.wav\n"
               f"  kg change-sound 8BitDo* /sounds/gamepad.mp3\n"
               f"  kg change-sound vendor:153* /sounds/razer.mp3\n"
               f"  kg update                  # Update Knocking Goose\n"
               f"  kg quack                   # Easter egg!\n"
               f"\nFor detailed manual: kg --man",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--man', action='store_true', help='Show manual')
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
        # Man page here (too long, keep separate)
        print("See --help for quick reference")
        return
    
    if args.version:
        show_version()
        return
    
    # Parse -connect and -disconnect flags
    connect_flag = '-connect' in args.args
    disconnect_flag = '-disconnect' in args.args
    
    # Remove flags from args
    filtered_args = [arg for arg in args.args if arg not in ['-connect', '-disconnect']]
    
    if args.command == 'change-sound':
        if len(filtered_args) < 2:
            print("Error: change-sound requires DEVICE and /path/to/sound")
            print("Flags: -connect (default), -disconnect")
            sys.exit(1)
        device_name = filtered_args[0]
        sound_path = filtered_args[1]
        # Default to connect if no flags specified
        if not connect_flag and not disconnect_flag:
            connect_flag = True
        change_sound(device_name, sound_path, connect_flag, disconnect_flag)
    elif args.command == 'update':
        update_knocking_goose()
    elif args.command == 'quack':
        easter_egg_quack()
    elif args.command == 'download-sounds':
        download_sounds()
    elif args.command == 'action':
        if len(filtered_args) < 2:
            print("Error: action requires DEVICE and /path/to/script.sh")
            sys.exit(1)
        set_action(filtered_args[0], filtered_args[1])
    elif args.command in ['colour', 'color']:
        if len(filtered_args) < 2:
            print("Error: colour requires DEVICE and COLOR")
            sys.exit(1)
        set_color(filtered_args[0], filtered_args[1])
    elif args.command in ['colours', 'colors']:
        show_colors()
    elif args.command == 'blacklist':
        if len(filtered_args) < 1:
            print("Error: blacklist requires DEVICE")
            sys.exit(1)
        remove = '--remove' in filtered_args
        device_name = filtered_args[1] if remove else filtered_args[0]
        manage_blacklist(device_name, remove)
    elif args.command == 'volume':
        if len(filtered_args) < 1:
            print("Error: volume requires NUMBER")
            sys.exit(1)
        set_volume(filtered_args[0])
    elif args.command == 'list':
        list_devices()
    elif args.command == 'history':
        days = int(filtered_args[0]) if filtered_args else 1
        show_history(days)
    elif args.command == 'stats':
        show_stats()
    elif args.command == 'remove':
        if len(filtered_args) < 2:
            print("Error: remove requires TYPE and DEVICE")
            sys.exit(1)
        remove_config(filtered_args[0], filtered_args[1])
    elif args.command == 'test-sound':
        if len(filtered_args) < 1:
            print("Error: test-sound requires DEVICE")
            sys.exit(1)
        event_type = 'disconnect' if disconnect_flag else 'connect'
        test_sound(filtered_args[0], event_type)
    elif args.command:
        print(f"Error: Unknown command '{args.command}'")
        sys.exit(1)
    else:
        # Play startup sound
        if os.path.exists(SOUND_START):
            play_sound(SOUND_START, load_config().get('volume', 100))
        
        print(colorize("Starting Knocking Goose v5.0...", Colors.BRIGHT_CYAN))
        config = load_config()
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
