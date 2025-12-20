# knock_gui.py
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import json
import os

class KnockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Knock")
        self.config = self.load_config()

        # Hauptframe
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Allgemeine Sounds
        self.general_frame = tk.LabelFrame(self.main_frame, text="General Sounds")
        self.general_frame.pack(fill=tk.X, padx=5, pady=5)

        self.connect_sound_label = tk.Label(self.general_frame, text="Connect Sound:")
        self.connect_sound_label.grid(row=0, column=0, padx=5, pady=5)
        self.connect_sound_entry = tk.Entry(self.general_frame)
        self.connect_sound_entry.grid(row=0, column=1, padx=5, pady=5)
        self.connect_sound_button = tk.Button(self.general_frame, text="Browse", command=self.browse_connect_sound)
        self.connect_sound_button.grid(row=0, column=2, padx=5, pady=5)

        self.disconnect_sound_label = tk.Label(self.general_frame, text="Disconnect Sound:")
        self.disconnect_sound_label.grid(row=1, column=0, padx=5, pady=5)
        self.disconnect_sound_entry = tk.Entry(self.general_frame)
        self.disconnect_sound_entry.grid(row=1, column=1, padx=5, pady=5)
        self.disconnect_sound_button = tk.Button(self.general_frame, text="Browse", command=self.browse_disconnect_sound)
        self.disconnect_sound_button.grid(row=1, column=2, padx=5, pady=5)

        # Gerätespezifische Sounds
        self.device_frame = tk.LabelFrame(self.main_frame, text="Device Specific Sounds")
        self.device_frame.pack(fill=tk.BOTH, padx=5, pady=5)

        self.device_listbox = tk.Listbox(self.device_frame)
        self.device_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.device_listbox.bind('<<ListboxSelect>>', self.on_device_select)

        self.add_device_button = tk.Button(self.device_frame, text="Add Device", command=self.add_device)
        self.add_device_button.pack(side=tk.LEFT, padx=5, pady=5)
        self.remove_device_button = tk.Button(self.device_frame, text="Remove Device", command=self.remove_device)
        self.remove_device_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Sound-Einstellungen für das ausgewählte Gerät
        self.device_sound_frame = tk.Frame(self.device_frame)
        self.device_sound_frame.pack(fill=tk.X, padx=5, pady=5)

        self.device_connect_sound_label = tk.Label(self.device_sound_frame, text="Connect Sound:")
        self.device_connect_sound_label.grid(row=0, column=0, padx=5, pady=5)
        self.device_connect_sound_entry = tk.Entry(self.device_sound_frame)
        self.device_connect_sound_entry.grid(row=0, column=1, padx=5, pady=5)
        self.device_connect_sound_button = tk.Button(self.device_sound_frame, text="Browse", command=self.browse_device_connect_sound)
        self.device_connect_sound_button.grid(row=0, column=2, padx=5, pady=5)

        self.device_disconnect_sound_label = tk.Label(self.device_sound_frame, text="Disconnect Sound:")
        self.device_disconnect_sound_label.grid(row=1, column=0, padx=5, pady=5)
        self.device_disconnect_sound_entry = tk.Entry(self.device_sound_frame)
        self.device_disconnect_sound_entry.grid(row=1, column=1, padx=5, pady=5)
        self.device_disconnect_sound_button = tk.Button(self.device_sound_frame, text="Browse", command=self.browse_device_disconnect_sound)
        self.device_disconnect_sound_button.grid(row=1, column=2, padx=5, pady=5)

        # Speichern-Button
        self.save_button = tk.Button(self.main_frame, text="Save", command=self.save_config)
        self.save_button.pack(pady=5)

        # Laden der Konfiguration
        self.load_config_ui()

    def load_config(self):
        config_file = 'config.json'
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

    def load_config_ui(self):
        self.connect_sound_entry.delete(0, tk.END)
        self.connect_sound_entry.insert(0, self.config.get('general_sound_connect', ''))

        self.disconnect_sound_entry.delete(0, tk.END)
        self.disconnect_sound_entry.insert(0, self.config.get('general_sound_disconnect', ''))

        self.device_listbox.delete(0, tk.END)
        for device_id, sounds in self.config.get('device_specific_sounds', {}).items():
            self.device_listbox.insert(tk.END, device_id)

    def browse_connect_sound(self):
        file_path = filedialog.askopenfilename(filetypes=[("Sound Files", "*.mp3 *.wav *.ogg")])
        if file_path:
            self.connect_sound_entry.delete(0, tk.END)
            self.connect_sound_entry.insert(0, file_path)

    def browse_disconnect_sound(self):
        file_path = filedialog.askopenfilename(filetypes=[("Sound Files", "*.mp3 *.wav *.ogg")])
        if file_path:
            self.disconnect_sound_entry.delete(0, tk.END)
            self.disconnect_sound_entry.insert(0, file_path)

    def browse_device_connect_sound(self):
        file_path = filedialog.askopenfilename(filetypes=[("Sound Files", "*.mp3 *.wav *.ogg")])
        if file_path:
            self.device_connect_sound_entry.delete(0, tk.END)
            self.device_connect_sound_entry.insert(0, file_path)

    def browse_device_disconnect_sound(self):
        file_path = filedialog.askopenfilename(filetypes=[("Sound Files", "*.mp3 *.wav *.ogg")])
        if file_path:
            self.device_disconnect_sound_entry.delete(0, tk.END)
            self.device_disconnect_sound_entry.insert(0, file_path)

    def on_device_select(self, event):
        selection = self.device_listbox.curselection()
        if selection:
            device_id = self.device_listbox.get(selection[0])
            sounds = self.config.get('device_specific_sounds', {}).get(device_id, {})
            self.device_connect_sound_entry.delete(0, tk.END)
            self.device_connect_sound_entry.insert(0, sounds.get('connect', ''))
            self.device_disconnect_sound_entry.delete(0, tk.END)
            self.device_disconnect_sound_entry.insert(0, sounds.get('disconnect', ''))

    def add_device(self):
        device_id = simpledialog.askstring("Add Device", "Enter Device ID:")
        if device_id:
            if device_id not in self.config.get('device_specific_sounds', {}):
                self.config.setdefault('device_specific_sounds', {})[device_id] = {'connect': '', 'disconnect': ''}
                self.device_listbox.insert(tk.END, device_id)

    def remove_device(self):
        selection = self.device_listbox.curselection()
        if selection:
            device_id = self.device_listbox.get(selection[0])
            del self.config['device_specific_sounds'][device_id]
            self.device_listbox.delete(selection[0])
            self.device_connect_sound_entry.delete(0, tk.END)
            self.device_disconnect_sound_entry.delete(0, tk.END)

    def save_config(self):
        self.config['general_sound_connect'] = self.connect_sound_entry.get()
        self.config['general_sound_disconnect'] = self.disconnect_sound_entry.get()

        selection = self.device_listbox.curselection()
        if selection:
            device_id = self.device_listbox.get(selection[0])
            self.config['device_specific_sounds'][device_id] = {
                'connect': self.device_connect_sound_entry.get(),
                'disconnect': self.device_disconnect_sound_entry.get()
            }

        with open('config.json', 'w') as f:
            json.dump(self.config, f)
        messagebox.showinfo("Success", "Configuration saved successfully.")

def start_gui():
    root = tk.Tk()
    app = KnockApp(root)
    root.mainloop()

if __name__ == '__main__':
    start_gui()