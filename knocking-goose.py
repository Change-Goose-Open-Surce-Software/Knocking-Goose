#!/usr/bin/env python3
# knocking-goose.py
import json
import os
import sys
import argparse
import threading
import time
import subprocess
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import pyudev

# Initialize GStreamer
Gst.init(None)

# Global variable to track recent events (avoid duplicates)
recent_events = []
event_lock = threading.Lock()

# Debug mode
debug_mode = False

# Konfiguration laden oder erstellen
def load_config():
    config_file = os.path.expanduser('~/.config/kg_config.json')
    default_config = {
        'disconnect_sound': None,
        'device_connect_sounds': {},
        'vendor_connect_sounds': {},  # NEU: Hersteller-spezifische Sounds
        'device_actions': {},  # NEU: Scripts bei Connect
        'volume': 100,  # NEU: Lautstärke in Prozent
        'profiles': {  # NEU: Profile
            'default': {
                'disconnect_sound': None,
                'volume': 100
            }
        },
        'active_profile': 'default',
        'blacklist': []  # NEU: Blacklist für Geräte
    }
    
    # Create config directory if it doesn't exist
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
        
        # Migration: Convert old format to new format
        if 'general_sound_disconnect' in config or 'general_sound_connect' in config:
            print("Migrating old config format...")
            new_config = default_config.copy()
            new_config['disconnect_sound'] = config.get('general_sound_disconnect')
            
            # Convert old device_specific_sounds
            if 'device_specific_sounds' in config:
                for device_id, sounds in config['device_specific_sounds'].items():
                    if isinstance(sounds, dict) and 'connect' in sounds:
                        new_config['device_connect_sounds'][device_id] = sounds['connect']
            
            # Save migrated config
            with open(config_file, 'w') as f:
                json.dump(new_config, f, indent=4)
            return new_config
        
        # Ensure all required keys exist
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

# Sound abspielen mit Lautstärke-Kontrolle
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

# Script ausführen
def run_action(script_path, device_id):
    if script_path and os.path.exists(script_path):
        try:
            if debug_mode:
                print(f"Running action: {script_path} for device: {device_id}")
            subprocess.Popen([script_path, device_id])
        except Exception as e:
            print(f"Error running action: {e}")

# Vendor ID aus device extrahieren
def get_vendor_id(device):
    vendor = device.get('ID_VENDOR_ID', '')
    return vendor if vendor else None

# Prüfen ob Event kürzlich schon aufgetreten ist (Duplikate vermeiden)
def is_duplicate_event(action, device_id, window=0.5):
    """Prüft ob ein Event innerhalb des Zeitfensters schon aufgetreten ist"""
    global recent_events
    current_time = time.time()
    event_key = f"{action}:{device_id}"
    
    with event_lock:
        # Alte Events entfernen
        recent_events = [(t, k) for t, k in recent_events if current_time - t < window]
        
        # Prüfen ob Event bereits existiert
        for _, key in recent_events:
            if key == event_key:
                return True
        
        # Event hinzufügen
        recent_events.append((current_time, event_key))
        return False

# USB-Geräte überwachen
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
            print(f"DEBUG: All device attributes: {dict(device)}")
        
        # Blacklist prüfen
        if device_id in config.get('blacklist', []):
            if debug_mode:
                print(f"DEBUG: Device {device_id} is blacklisted, ignoring")
            return
        
        # Filter anwenden
        if hide_default and device_id == 'default':
            return
        if hide_devices and device_id != 'default':
            return
        
        # Duplikate vermeiden (außer mit -all)
        if not show_all_duplicates:
            if is_duplicate_event(action, device_id):
                return
        
        if action == 'add':
            if hide_connects:
                return
            print(f"USB device connected: {device_id}")
            if vendor_id:
                print(f"  Vendor ID: {vendor_id}")
            
            # Sound abspielen: Priorität: Gerät > Hersteller > Default
            sound_file = None
            if device_id in config['device_connect_sounds']:
                sound_file = config['device_connect_sounds'][device_id]
            elif vendor_id and vendor_id in config.get('vendor_connect_sounds', {}):
                sound_file = config['vendor_connect_sounds'][vendor_id]
            
            if sound_file:
                play_sound(sound_file, config.get('volume', 100))
            
            # Action ausführen
            if device_id in config.get('device_actions', {}):
                run_action(config['device_actions'][device_id], device_id)
        else:
            if hide_disconnects:
                return
            print(f"USB device disconnected: {device_id}")
            # Einheitlicher Disconnect-Sound
            sound_file = config['disconnect_sound']
            if sound_file:
                play_sound(sound_file, config.get('volume', 100))

    for device in iter(monitor.poll, None):
        if device.action == 'add':
            handle_device_event('add', device)
        elif device.action == 'remove':
            handle_device_event('remove', device)

# Sound ändern
def change_sound(device_name, sound_path):
    config = load_config()
    
    if not os.path.exists(sound_path):
        print(f"Error: Sound file not found: {sound_path}")
        return
    
    if device_name == '!':
        # Disconnect-Sound
        config['disconnect_sound'] = sound_path
        print(f"Disconnect sound set to: {sound_path}")
    elif device_name.startswith('vendor:'):
        # Vendor-Sound
        vendor_id = device_name.split(':', 1)[1]
        config['vendor_connect_sounds'][vendor_id] = sound_path
        print(f"Connect sound for vendor '{vendor_id}' set to: {sound_path}")
    else:
        # Connect-Sound für spezifisches Gerät
        config['device_connect_sounds'][device_name] = sound_path
        print(f"Connect sound for '{device_name}' set to: {sound_path}")
    
    save_config(config)

# Action setzen
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

# Blacklist verwalten
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

# Lautstärke setzen
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

# Geräte auflisten
def list_devices():
    context = pyudev.Context()
    print("\n" + "=" * 70)
    print("Currently connected USB devices:")
    print("=" * 70)
    
    for device in context.list_devices(subsystem='usb'):
        device_id = device.get('ID_SERIAL', 'default')
        vendor_id = device.get('ID_VENDOR_ID', 'N/A')
        product_id = device.get('ID_MODEL_ID', 'N/A')
        vendor_name = device.get('ID_VENDOR', 'Unknown')
        model_name = device.get('ID_MODEL', 'Unknown')
        
        if device_id != 'default':
            print(f"\nDevice: {device_id}")
            print(f"  Vendor: {vendor_name} ({vendor_id})")
            print(f"  Model: {model_name} ({product_id})")
    
    print("=" * 70 + "\n")

# Sound testen
def test_sound(device_name):
    config = load_config()
    
    if device_name == '!':
        sound_file = config['disconnect_sound']
        print(f"Testing disconnect sound...")
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

# Terminal-Oberfläche
def main():
    global debug_mode
    
    parser = argparse.ArgumentParser(
        description='Knocking Goose - USB Device Sound Notifier',
        add_help=True
    )
    parser.add_argument('--man', action='store_true', help='Show manual')
    parser.add_argument('--version', action='version', version='Knocking Goose 3.0')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('-d', '--hide-disconnects', action='store_true', help='Hide disconnect messages')
    parser.add_argument('-c', '--hide-connects', action='store_true', help='Hide connect messages')
    parser.add_argument('-default', '--hide-default', action='store_true', help='Hide "default" devices')
    parser.add_argument('-device', '--hide-devices', action='store_true', help='Hide all non-default devices')
    parser.add_argument('-all', '--show-all', action='store_true', help='Show all events (including duplicates)')
    parser.add_argument('command', nargs='?', help='Command')
    parser.add_argument('args', nargs='*', help='Command arguments')
    
    args = parser.parse_args()
    
    if args.debug:
        debug_mode = True
        print("DEBUG MODE ENABLED")

    if args.man:
        print("=" * 70)
        print("Manual for Knocking Goose")
        print("=" * 70)
        print("\nNAME")
        print("    kg - Knocking Goose USB Device Sound Notifier")
        print("\nSYNOPSIS")
        print("    kg [OPTIONS]")
        print("    kg change-sound [DEVICE|vendor:XXXX|!] /path/to/sound.mp3")
        print("    kg action DEVICE /path/to/script.sh")
        print("    kg blacklist DEVICE")
        print("    kg volume NUMBER")
        print("    kg list")
        print("    kg test-sound [DEVICE|vendor:XXXX|!]")
        print("\nCOMMANDS")
        print("    change-sound [DEVICE|vendor:XXXX|!] /path/to/sound.mp3")
        print("        Set sound for device, vendor, or disconnect")
        print("        Examples:")
        print("            kg change-sound 8BitDo_IDLE /sounds/gamepad.mp3")
        print("            kg change-sound vendor:1532 /sounds/razer.mp3")
        print("            kg change-sound ! /sounds/disconnect.mp3")
        print("")
        print("    action DEVICE /path/to/script.sh")
        print("        Execute script when device connects")
        print("        Example:")
        print("            kg action 8BitDo_IDLE /home/user/gaming.sh")
        print("")
        print("    blacklist DEVICE")
        print("        Add device to blacklist (no sounds/actions)")
        print("        Example:")
        print("            kg blacklist default")
        print("")
        print("    blacklist --remove DEVICE")
        print("        Remove device from blacklist")
        print("")
        print("    volume NUMBER")
        print("        Set volume (0-100)")
        print("        Example:")
        print("            kg volume 50")
        print("")
        print("    list")
        print("        Show all connected USB devices")
        print("")
        print("    test-sound [DEVICE|vendor:XXXX|!]")
        print("        Test sound without connecting device")
        print("\nOPTIONS")
        print("    --debug")
        print("        Enable debug mode (shows all USB events)")
        print("    -d, --hide-disconnects")
        print("        Hide disconnect messages")
        print("    -c, --hide-connects")
        print("        Hide connect messages")
        print("    -default, --hide-default")
        print("        Hide 'default' device messages")
        print("    -device, --hide-devices")
        print("        Hide all non-default device messages")
        print("    -all, --show-all")
        print("        Show all events (including duplicates)")
        print("\nCONFIGURATION")
        print("    Config file: ~/.config/kg_config.json")
        print("\nAUTHOR")
        print("    Change-Goose-Open-Source-Software")
        print("=" * 70)
        return

    # Command handling
    if args.command == 'change-sound':
        if len(args.args) < 2:
            print("Error: change-sound requires [DEVICE] and /path/to/sound")
            sys.exit(1)
        device_name = args.args[0]
        sound_path = args.args[1]
        change_sound(device_name, sound_path)
    elif args.command == 'action':
        if len(args.args) < 2:
            print("Error: action requires DEVICE and /path/to/script.sh")
            sys.exit(1)
        device_name = args.args[0]
        script_path = args.args[1]
        set_action(device_name, script_path)
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
        # Starte den Hintergrundprozess zur Überwachung von USB-Geräten
        print("Starting Knocking Goose...")
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
        
        monitor_thread = threading.Thread(
            target=monitor_usb,
            args=(args.hide_connects, args.hide_disconnects, args.hide_default, args.hide_devices, args.show_all)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
        
        print("Knocking Goose is running in the background.")
        print("Press Ctrl+C to stop.")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping Knocking Goose...")

if __name__ == '__main__':
    main()
