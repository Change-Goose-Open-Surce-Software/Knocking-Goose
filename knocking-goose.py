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

# Konfiguration laden oder erstellen
def load_config():
    config_file = os.path.expanduser('~/.config/kg_config.json')
    default_config = {
        'general_sound_connect': None,
        'general_sound_disconnect': None,
        'device_specific_sounds': {}
    }
    
    # Create config directory if it doesn't exist
    config_dir = os.path.dirname(config_file)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    else:
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

# Sound abspielen
def play_sound(sound_file):
    if sound_file and os.path.exists(sound_file):
        try:
            # Use GStreamer to play the sound
            player = Gst.ElementFactory.make("playbin", "player")
            player.set_property("uri", "file://" + os.path.abspath(sound_file))
            player.set_state(Gst.State.PLAYING)
            # Wait for the sound to finish playing
            bus = player.get_bus()
            bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
            player.set_state(Gst.State.NULL)
        except Exception as e:
            print(f"Error playing sound: {e}")

# USB-Geräte überwachen
def monitor_usb():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('usb')
    
    def handle_device_event(action, device):
        config = load_config()
        device_id = device.get('ID_SERIAL', 'default')
        if action == 'add':
            sound_file = config['device_specific_sounds'].get(device_id, {}).get('connect', config['general_sound_connect'])
            print(f"USB device connected: {device_id}")
        else:
            sound_file = config['device_specific_sounds'].get(device_id, {}).get('disconnect', config['general_sound_disconnect'])
            print(f"USB device disconnected: {device_id}")
        
        if sound_file:
            play_sound(sound_file)

    for device in iter(monitor.poll, None):
        if device.action == 'add':
            handle_device_event('add', device)
        elif device.action == 'remove':
            handle_device_event('remove', device)

# Terminal-Oberfläche
def main():
    parser = argparse.ArgumentParser(
        description='Knocking Goose - USB Device Sound Notifier',
        add_help=True
    )
    parser.add_argument('--man', action='store_true', help='Show manual')
    parser.add_argument('--version', action='version', version='Knocking Goose 1.0')
    
    args = parser.parse_args()

    if args.man:
        print("=" * 60)
        print("Manual for Knocking Goose")
        print("=" * 60)
        print("\nNAME")
        print("    kg - Knocking Goose USB Device Sound Notifier")
        print("\nSYNOPSIS")
        print("    kg [OPTIONS]")
        print("\nDESCRIPTION")
        print("    Knocking Goose monitors USB device connections and plays")
        print("    custom sounds when devices are connected or disconnected.")
        print("\nOPTIONS")
        print("    -h, --help")
        print("        Show help message and exit")
        print("\n    --man")
        print("        Show this manual")
        print("\n    --version")
        print("        Show version information")
        print("\nCONFIGURATION")
        print("    Config file: ~/.config/kg_config.json")
        print("\nEXAMPLES")
        print("    kg")
        print("        Start monitoring USB devices")
        print("\n    kg --man")
        print("        Show this manual")
        print("\nAUTHOR")
        print("    Change-Goose-Open-Source-Software")
        print("=" * 60)
    else:
        # Starte den Hintergrundprozess zur Überwachung von USB-Geräten
        print("Starting Knocking Goose...")
        print(f"Config file: {os.path.expanduser('~/.config/kg_config.json')}")
        
        monitor_thread = threading.Thread(target=monitor_usb)
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
