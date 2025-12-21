#!/usr/bin/env python3
# knocking-goose.py v3.2
import json
import os
import sys
import argparse
import threading
import time
import subprocess
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

# ANSI Color codes
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

def load_config():
    config_file = os.path.expanduser('~/.config/kg_config.json')
    default_config = {
        'disconnect_sound': None, 'device_connect_sounds': {}, 'vendor_connect_sounds': {},
        'device_actions': {}, 'device_colors': {}, 'vendor_colors': {}, 'volume': 100,
        'profiles': {'default': {'disconnect_sound': None, 'volume': 100}},
        'active_profile': 'default', 'blacklist': [], 'history': []
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
        
        if 'general_sound_disconnect' in config or 'general_sound_connect' in config:
            print("Migrating old config format...")
            new_config = default_config.copy()
            new_config['disconnect_sound'] = config.get('general_sound_disconnect')
            if 'device_specific_sounds' in config:
                for device_id, sounds in config['device_specific_sounds'].items():
                    if isinstance(sounds, dict) and 'connect' in sounds:
                        new_config['device_connect_sounds'][device_id] = sounds['connect']
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

def colorize(text, color_code):
    return f"{color_code}{text}{Colors.RESET}"

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

def monitor_usb(hide_connects=False, hide_disconnects=False, hide_default=False, hide_devices=False, show_all_duplicates=False):
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('usb')
    
    def handle_device_event(action, device):
        config = load_config()
        device_id = device.get('ID_SERIAL', 'default')
        vendor_id = get_vendor_id(device)
        
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
                sound_file = config['device_connect_sounds'].get(device_id) or (config.get('vendor_connect_sounds', {}).get(vendor_id) if vendor_id else None)
                if sound_file:
                    play_sound(sound_file, config.get('volume', 100))
                if device_id in config.get('device_actions', {}):
                    run_action(config['device_actions'][device_id], device_id)
        else:
            if not hide_disconnects:
                print(colorize(f"○ USB device disconnected: {device_id}", Colors.DIM + color))
                log_event(device_id, 'remove', vendor_id)
                if config['disconnect_sound']:
                    play_sound(config['disconnect_sound'], config.get('volume', 100))

    for device in iter(monitor.poll, None):
        if device.action == 'add':
            handle_device_event('add', device)
        elif device.action == 'remove':
            handle_device_event('remove', device)

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

def change_sound(device_name, sound_path):
    config = load_config()
    if not os.path.exists(sound_path):
        print(f"Error: Sound file not found: {sound_path}")
        return
    if device_name == '!':
        config['disconnect_sound'] = sound_path
        print(f"Disconnect sound set to: {sound_path}")
    elif device_name.startswith('vendor:'):
        vendor_id = device_name.split(':', 1)[1]
        config['vendor_connect_sounds'][vendor_id] = sound_path
        print(f"Connect sound for vendor '{vendor_id}' set to: {sound_path}")
    else:
        config['device_connect_sounds'][device_name] = sound_path
        print(f"Connect sound for '{device_name}' set to: {sound_path}")
    save_config(config)

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
        if device_name == '!':
            config['disconnect_sound'] = None
            print("Disconnect sound removed")
        elif device_name.startswith('vendor:'):
            vendor_id = device_name.split(':', 1)[1]
            if vendor_id in config.get('vendor_connect_sounds', {}):
                del config['vendor_connect_sounds'][vendor_id]
                print(f"Vendor sound for '{vendor_id}' removed")
            else:
                print(f"No sound configured for vendor '{vendor_id}'")
                return
        else:
            if device_name in config.get('device_connect_sounds', {}):
                del config['device_connect_sounds'][device_name]
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
    print(f"\n{colorize('Current Version:', Colors.BOLD)} {colorize('4.0', Colors.BRIGHT_GREEN)}")
    print(f"{colorize('Release Date:', Colors.BOLD)} 2025-12-22 02:00")
    print("\n" + "=" * 70)
    print(colorize("VERSION HISTORY", Colors.BOLD + Colors.BRIGHT_YELLOW))
    print("=" * 70)
    versions = [
        {'version': '4.0', 'date': '2025-12-22 02:00', 'changes': [
            'System-wide autostart for ALL users via /etc/xdg/autostart/',
            'New kg_start.sh script for startup management',
            'Auto-updater integration with kg_start.sh',
            'No more per-user configuration needed',
            'Automatic installation of startup files',
            'Works across all desktop environments system-wide']},
        {'version': '3.2', 'date': '2025-12-22 01:00', 'changes': [
            'Added color support for devices and vendors', 'Colorful output for history, stats, and monitoring',
            'Fixed autostart issues with systemd service', 'Better autostart wrapper with delay',
            'Service status check after installation', 'Show all available colors with examples']},
        {'version': '3.1', 'date': '2025-12-22 00:15', 'changes': [
            'Improved autostart installation script', 'Support for all major Linux desktop environments']},
        {'version': '3.0', 'date': '2025-12-21 23:45', 'changes': [
            'Added vendor-specific sounds', 'Added action scripts', 'Added device history', 'Added statistics']},
        {'version': '2.0', 'date': '2025-12-21 22:30', 'changes': ['Complete rewrite', 'Filter options']},
        {'version': '1.0', 'date': '2025-12-21 20:00', 'changes': ['Initial release']}
    ]
    for v in versions:
        print(f"\n{colorize('Version ' + v['version'], Colors.BOLD + Colors.BRIGHT_GREEN)} - {v['date']}")
        print("-" * 70)
        for change in v['changes']:
            print(f"  {colorize('•', Colors.BRIGHT_YELLOW)} {change}")
    print("\n" + "=" * 70)

def test_sound(device_name):
    config = load_config()
    if device_name == '!':
        sound_file = config['disconnect_sound']
        print("Testing disconnect sound...")
    elif device_name.startswith('vendor:'):
        vendor_id = device_name.split(':', 1)[1]
        sound_file = config.get('vendor_connect_sounds', {}).get(vendor_id)
        print(f"Testing vendor sound for {vendor_id}...")
    else:
        sound_file = config['device_connect_sounds'].get(device_name)
        print(f"Testing connect sound for {device_name}...")
    if sound_file:
        print(f"Playing: {sound_file}")
        play_sound(sound_file, config.get('volume', 100))
    else:
        print("No sound configured for this device/vendor")

def main():
    global debug_mode
    parser = argparse.ArgumentParser(description='Knocking Goose - USB Device Sound Notifier', add_help=True)
    parser.add_argument('--man', action='store_true', help='Show manual')
    parser.add_argument('--version', action='store_true', help='Show version information')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('-d', '--hide-disconnects', action='store_true', help='Hide disconnect messages')
    parser.add_argument('-c', '--hide-connects', action='store_true', help='Hide connect messages')
    parser.add_argument('-default', '--hide-default', action='store_true', help='Hide "default" devices')
    parser.add_argument('-device', '--hide-devices', action='store_true', help='Hide all non-default devices')
    parser.add_argument('-all', '--show-all', action='store_true', help='Show all events')
    parser.add_argument('command', nargs='?', help='Command')
    parser.add_argument('args', nargs='*', help='Command arguments')
    args = parser.parse_args()
    
    if args.debug:
        debug_mode = True
        print(colorize("DEBUG MODE ENABLED", Colors.BRIGHT_YELLOW))
    if args.man:
        print("=" * 70)
        print(colorize("Manual for Knocking Goose", Colors.BOLD + Colors.BRIGHT_CYAN))
        print("=" * 70)
        print("\nNAME\n    kg - Knocking Goose USB Device Sound Notifier")
        print("\nCOMMANDS")
        print("    " + colorize("colour [DEVICE|vendor:XXXX] COLOR", Colors.BRIGHT_GREEN))
        print("        Set color for device or vendor")
        print("        Examples: kg colour default red, kg colour vendor:1532 gray")
        print("\n    " + colorize("colours", Colors.BRIGHT_GREEN))
        print("        Show all available colors")
        print("\nFor full manual: kg --help")
        print("=" * 70)
        return
    if args.version:
        show_version()
        return
    
    if args.command == 'change-sound':
        if len(args.args) < 2:
            print("Error: change-sound requires [DEVICE] and /path/to/sound")
            sys.exit(1)
        change_sound(args.args[0], args.args[1])
    elif args.command == 'action':
        if len(args.args) < 2:
            print("Error: action requires DEVICE and /path/to/script.sh")
            sys.exit(1)
        set_action(args.args[0], args.args[1])
    elif args.command in ['colour', 'color']:
        if len(args.args) < 2:
            print("Error: colour requires [DEVICE|vendor:XXXX] and COLOR")
            print("\nShow available colors with: kg colours")
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
            print("Error: volume requires NUMBER (0-100)")
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
            print("Error: remove requires [sound|action|colour] and [DEVICE|vendor:XXXX|!]")
            sys.exit(1)
        config_type = args.args[0]
        device_name = args.args[1]
        if config_type not in ['sound', 'action', 'color', 'colour']:
            print("Error: first argument must be 'sound', 'action', or 'colour'")
            sys.exit(1)
        remove_config(config_type, device_name)
    elif args.command == 'test-sound':
        if len(args.args) < 1:
            print("Error: test-sound requires [DEVICE|vendor:XXXX|!]")
            sys.exit(1)
        test_sound(args.args[0])
    elif args.command:
        print(f"Error: Unknown command '{args.command}'")
        print("Use 'kg --help' for available commands")
        sys.exit(1)
    else:
        print(colorize("Starting Knocking Goose...", Colors.BRIGHT_CYAN))
        print(f"Config file: {os.path.expanduser('~/.config/kg_config.json')}")
        filters = []
        if args.hide_connects:
            filters.append("hiding connects")
        if args.hide_disconnects:
            filters.append("hiding disconnects")
        if args.hide_default:
            filters.append("hiding 'default' devices")
        if args.hide_devices:
            filters.append("hiding non-default devices")
        if args.show_all:
            filters.append("showing all duplicates")
        if debug_mode:
            filters.append("DEBUG MODE")
        if filters:
            print(f"Filters: {', '.join(filters)}")
        config = load_config()
        print(f"Volume: {config.get('volume', 100)}%")
        monitor_thread = threading.Thread(target=monitor_usb, args=(args.hide_connects, args.hide_disconnects, args.hide_default, args.hide_devices, args.show_all))
        monitor_thread.daemon = True
        monitor_thread.start()
        print(colorize("Knocking Goose is running in the background.", Colors.BRIGHT_GREEN))
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(colorize("\nStopping Knocking Goose...", Colors.BRIGHT_YELLOW))

if __name__ == '__main__':
    main()
