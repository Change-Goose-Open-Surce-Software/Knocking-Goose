#!/usr/bin/env python3
# Knocking Goose v4.1

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime, timedelta

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import pyudev

# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------

BASE_DIR = "/usr/share/knocking-goose7"
SOUND_DIR = f"{BASE_DIR}/sounds"

START_SOUND = f"{SOUND_DIR}/Start.mp3"
OFF_SOUND   = f"{SOUND_DIR}/Off.mp3"
QUARK_SOUND = f"{SOUND_DIR}/Quark.mp3"

CONFIG_FILE = os.path.expanduser("~/.config/kg_config.json")

Gst.init(None)
known_devices = {}

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

def default_config():
    return {
        "version": "4.1",
        "volume": 100,
        "connect_sounds": {},
        "disconnect_sounds": {},
        "vendor_connect_sounds": {},
        "vendor_disconnect_sounds": {},
        "history": []
    }

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config())
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

# --------------------------------------------------
# SOUND
# --------------------------------------------------

def play_sound(path, volume):
    if not path or not os.path.exists(path):
        return
    try:
        player = Gst.ElementFactory.make("playbin", None)
        player.set_property("uri", "file://" + os.path.abspath(path))
        player.set_property("volume", volume / 100.0)
        player.set_state(Gst.State.PLAYING)
        bus = player.get_bus()
        bus.poll(Gst.MessageType.EOS, Gst.CLOCK_TIME_NONE)
        player.set_state(Gst.State.NULL)
    except Exception:
        pass

# --------------------------------------------------
# DEVICE SNAPSHOT (FIX DEFAULT BUG)
# --------------------------------------------------

def snapshot_devices():
    ctx = pyudev.Context()
    devices = {}
    for d in ctx.list_devices(subsystem="usb"):
        serial = d.get("ID_SERIAL")
        if serial:
            devices[serial] = {
                "vendor": d.get("ID_VENDOR_ID"),
                "name": d.get("ID_VENDOR", "Unknown")
            }
    return devices

# --------------------------------------------------
# MATCHING
# --------------------------------------------------

def matches(pattern, value):
    if not value:
        return False
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return pattern == value

# --------------------------------------------------
# HISTORY
# --------------------------------------------------

def log_history(device, action, vendor):
    cfg = load_config()
    cfg["history"].append({
        "time": datetime.now().isoformat(),
        "device": device,
        "action": action,
        "vendor": vendor
    })
    cfg["history"] = cfg["history"][-1000:]
    save_config(cfg)

# --------------------------------------------------
# MONITOR
# --------------------------------------------------

def monitor():
    global known_devices
    ctx = pyudev.Context()
    mon = pyudev.Monitor.from_netlink(ctx)
    mon.filter_by("usb")

    for dev in iter(mon.poll, None):
        cfg = load_config()
        vol = cfg["volume"]

        if dev.action == "add":
            known_devices = snapshot_devices()
            device = dev.get("ID_SERIAL")
            vendor = dev.get("ID_VENDOR_ID")

            for p, s in cfg["connect_sounds"].items():
                if matches(p, device):
                    play_sound(s, vol)

            for p, s in cfg["vendor_connect_sounds"].items():
                if matches(p, vendor):
                    play_sound(s, vol)

            log_history(device, "connect", vendor)

        elif dev.action == "remove":
            new = snapshot_devices()
            missing = set(known_devices) - set(new)

            if missing:
                device = list(missing)[0]
                vendor = known_devices[device]["vendor"]
            else:
                device = "unknown"
                vendor = None

            for p, s in cfg["disconnect_sounds"].items():
                if matches(p, device):
                    play_sound(s, vol)

            for p, s in cfg["vendor_disconnect_sounds"].items():
                if matches(p, vendor):
                    play_sound(s, vol)

            log_history(device, "disconnect", vendor)
            known_devices = new

# --------------------------------------------------
# COMMANDS
# --------------------------------------------------

def cmd_change_sound(args):
    cfg = load_config()
    modes = {"connect": False, "disconnect": False}
    rest = []

    for a in args:
        if a == "-connect":
            modes["connect"] = True
        elif a == "-disconnect":
            modes["disconnect"] = True
        else:
            rest.append(a)

    if len(rest) != 2:
        print("Usage: kg change-sound [-connect] [-disconnect] PATTERN SOUND")
        return

    pattern, sound = rest
    if not os.path.exists(sound):
        print("Sound file not found")
        return

    if modes["connect"]:
        cfg["connect_sounds"][pattern] = sound
    if modes["disconnect"]:
        cfg["disconnect_sounds"][pattern] = sound

    save_config(cfg)

def cmd_volume(v):
    cfg = load_config()
    cfg["volume"] = max(0, min(100, int(v)))
    save_config(cfg)

def cmd_history(days):
    cfg = load_config()
    cutoff = datetime.now() - timedelta(days=days)
    for h in cfg["history"]:
        t = datetime.fromisoformat(h["time"])
        if t >= cutoff:
            print(f"{t} | {h['action']} | {h['device']} | {h['vendor']}")

def cmd_update():
    subprocess.run([f"{BASE_DIR}/update.sh"])

def cmd_quark():
    cfg = load_config()
    play_sound(QUARK_SOUND, cfg["volume"])

def show_version():
    print("Knocking Goose")
    print("Version: 4.1\n")
    print("VERSION HISTORY")
    print("1.0  Initial release")
    print("2.0  Rewrite")
    print("3.0  Vendor sounds")
    print("3.2  Colors & stats")
    print("4.0  Startup/Shutdown sounds, wildcard support")
    print("4.1  Moved files to /usr/share/knocking-goose7, renamed scripts")

# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    global known_devices

    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", nargs="?")
    parser.add_argument("args", nargs="*")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    if args.version:
        show_version()
        return

    if args.cmd == "change-sound":
        cmd_change_sound(args.args)
        return
    if args.cmd == "volume":
        cmd_volume(args.args[0])
        return
    if args.cmd == "history":
        cmd_history(int(args.args[0]) if args.args else 1)
        return
    if args.cmd == "update":
        cmd_update()
        return
    if args.cmd == "quark":
        cmd_quark()
        return

    cfg = load_config()
    known_devices = snapshot_devices()
    play_sound(START_SOUND, cfg["volume"])

    try:
        monitor()
    except KeyboardInterrupt:
        play_sound(OFF_SOUND, cfg["volume"])

if __name__ == "__main__":
    main()
