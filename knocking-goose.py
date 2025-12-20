#!/usr/bin/env python3
# knocking-goose.py
import json
import os
import sys
import argparse
import threading
import time
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import pyudev

# Initialize GStreamer
Gst.init(None)

# Global variable to track recent events (avoid duplicates)
recent_events = []
event_lock = threading.Lock()

# Konfiguration laden oder erstellen
def load_config():
    config_file = os.path.expanduser('~/.config/kg_config.json')
    default_config = {
        'disconnect_sound': None,  # Einheitlicher Disconnect-Sound
        'device_connect_sounds': {}  # Gerätespezifische Connect-Sounds
    }
    
    # Create config directory if it doesn't exist
    config_dir = os.path.dirname(config_file)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        
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
        if 'disconnect_sound' not in config:
            config['disconnect_sound'] = None
        if 'device_connect_sounds' not in config:
            config['device_connect_sounds'] = {}
        
        return config
    else:
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_config(config):
    config_file = os.path.expanduser('~/.config/kg_config.json')
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)

# Sound abspielen
def play_sound(sound_file):
    if sound_file and os.path.exists(sound_file):
        try:
            player = Gst.ElementFactory.make("playbin", "player")
            player.set_property("uri", "file://" + os.path.abspath(sound_file))
            player.set_state(Gst.State.PLAYING)
            bus = player.get_bus()
            bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
            player.set_state(Gst.State.NULL)
        except Exception as e:
            print(f"Error playing sound: {e}")

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
            # Connect-Sound für spezifisches Gerät
            sound_file = config['device_connect_sounds'].get(device_id)
            if sound_file:
                play_sound(sound_file)
        else:
            if hide_disconnects:
                return
            print(f"USB device disconnected: {device_id}")
            # Einheitlicher Disconnect-Sound
            sound_file = config['disconnect_sound']
            if sound_file:
                play_sound(sound_file)

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
    else:
        # Connect-Sound für spezifisches Gerät
        config['device_connect_sounds'][device_name] = sound_path
        print(f"Connect sound for '{device_name}' set to: {sound_path}")
    
    save_config(config)

# Terminal-Oberfläche
def main():
    parser = argparse.ArgumentParser(
        description='Knocking Goose - USB Device Sound Notifier',
        add_help=True
    )
    parser.add_argument('--man', action='store_true', help='Show manual')
    parser.add_argument('--version', action='version', version='Knocking Goose 2.0')
    parser.add_argument('-d', '--hide-disconnects', action='store_true', help='Hide disconnect messages')
    parser.add_argument('-c', '--hide-connects', action='store_true', help='Hide connect messages')
    parser.add_argument('-default', '--hide-default', action='store_true', help='Hide "default" devices')
    parser.add_argument('-device', '--hide-devices', action='store_true', help='Hide all non-default devices')
    parser.add_argument('-all', '--show-all', action='store_true', help='Show all events (including duplicates)')
    parser.add_argument('command', nargs='?', help='Command: change-sound')
    parser.add_argument('args', nargs='*', help='Command arguments')
    
    args = parser.parse_args()

    if args.man:
        print("=" * 70)
        print("Manual for Knocking Goose")
        print("=" * 70)
        print("\nNAME")
        print("    kg - Knocking Goose USB Device Sound Notifier")
        print("\nSYNOPSIS")
        print("    kg [OPTIONS]")
        print("    kg change-sound [DEVICE|!|default] /path/to/sound.mp3")
        print("\nDESCRIPTION")
        print("    Knocking Goose monitors USB device connections and plays")
        print("    custom sounds when devices are connected or disconnected.")
        print("\nOPTIONS")
        print("    -h, --help")
        print("        Show help message and exit")
        print("\n    -d, --hide-disconnects")
        print("        Hide disconnect messages")
        print("\n    -c, --hide-connects")
        print("        Hide connect messages")
        print("\n    -default, --hide-default")
        print("        Hide 'default' device messages")
        print("\n    -device, --hide-devices")
        print("        Hide all non-default device messages")
        print("\n    -all, --show-all")
        print("        Show all events (including duplicate simultaneous events)")
        print("\n    --man")
        print("        Show this manual")
        print("\n    --version")
        print("        Show version information")
        print("\nCOMMANDS")
        print("    change-sound [DEVICE] /path/to/sound.mp3")
        print("        Set connect sound for a specific device")
        print("        Examples:")
        print("            kg change-sound 8BitDo_IDLE_E417 /sounds/gamepad.mp3")
        print("            kg change-sound default /sounds/generic.mp3")
        print("            kg change-sound ! /sounds/disconnect.mp3")
        print("        ")
        print("        Special device names:")
        print("            !       - Sets the disconnect sound (used for all)")
        print("            default - Sets sound for 'default' devices")
        print("\nCONFIGURATION")
        print("    Config file: ~/.config/kg_config.json")
        print("\nEXAMPLES")
        print("    kg")
        print("        Start monitoring all USB devices")
        print("\n    kg -default")
        print("        Monitor USB devices, hide 'default' messages")
        print("\n    kg -d -default")
        print("        Hide disconnects and 'default' devices")
        print("\n    kg change-sound ! /sounds/disconnect.wav")
        print("        Set disconnect sound")
        print("\nNOTES")
        print("    - Only the first event is shown when multiple devices")
        print("      connect/disconnect simultaneously (use -all to override)")
        print("    - Disconnect sound is universal for all devices")
        print("    - Connect sounds are device-specific")
        print("\nAUTHOR")
        print("    Change-Goose-Open-Source-Software")
        print("=" * 70)
        return

    # Command handling
    if args.command == 'change-sound':
        if len(args.args) < 2:
            print("Error: change-sound requires [DEVICE] and /path/to/sound")
            print("Usage: kg change-sound [DEVICE|!|default] /path/to/sound.mp3")
            sys.exit(1)
        device_name = args.args[0]
        sound_path = args.args[1]
        change_sound(device_name, sound_path)
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
        
        if filters:
            print(f"Filters: {', '.join(filters)}")
        
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
