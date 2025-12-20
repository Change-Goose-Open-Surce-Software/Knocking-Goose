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
    config_file = 'kg_config.json'
    default_config = {
        'general_sound_connect': None,
        'general_sound_disconnect': None,
        'device_specific_sounds': {}
    }
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    else:
        with open(config_file, 'w') as f:
            json.dump(default_config, f)
        return default_config

# Sound abspielen
def play_sound(sound_file):
    if sound_file and os.path.exists(sound_file):
        # Use GStreamer to play the sound
        player = Gst.ElementFactory.make("playbin", "player")
        player.set_property("uri", "file://" + sound_file)
        player.set_state(Gst.State.PLAYING)
        # Wait for the sound to finish playing
        bus = player.get_bus()
        bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
        player.set_state(Gst.State.NULL)

# USB-Geräte überwachen (Beispiel für Linux mit pyudev)
def monitor_usb():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by('usb')
    config = load_config()

    def handle_device_event(action, device):
        device_id = device.get('ID_SERIAL', 'default')
        if action == 'add':
            sound_file = config['device_specific_sounds'].get(device_id, {}).get('connect', config['general_sound_connect'])
        else:
            sound_file = config['device_specific_sounds'].get(device_id, {}).get('disconnect', config['general_sound_disconnect'])
        play_sound(sound_file)

    for device in iter(monitor.poll, None):
        if device.action == 'add':
            handle_device_event('add', device)
        elif device.action == 'remove':
            handle_device_event('remove', device)

# Terminal-Oberfläche
def main():
    parser = argparse.ArgumentParser(description='Knocking Goose - USB Device Sound Notifier')
    parser.add_argument('--help', action='store_true', help='Show this help message')
    parser.add_argument('--man', action='store_true', help='Show manual')
    args = parser.parse_args()

    if args.help:
        print("Usage: kg [OPTIONS]")
        print("Options:")
        print("  --help    Show this help message")
        print("  --man     Show manual")
    elif args.man:
        print("Manual for Knocking Goose:")
        print("  kg --help: Show help message")
        print("  kg --man: Show this manual")
    else:
        # Starte den Hintergrundprozess zur Überwachung von USB-Geräten
        monitor_thread = threading.Thread(target=monitor_usb)
        monitor_thread.daemon = True
        monitor_thread.start()
        print("Knocking Goose is running in the background. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping Knocking Goose...")

if __name__ == '__main__':
    main()