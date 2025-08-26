import customtkinter as ctk
from tkinter import filedialog, messagebox
import subprocess
import threading
import datetime
import os
import atexit
# --- New feature for volume ---
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

# --- CONFIG ---
FFPLAY_PATH = "ffplay"  # if ffplay is in PATH
LOG_FILE = "IPTV_Player.log"
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- Logging ---
def log(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] [{level}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

atexit.register(lambda: log("Application closed", "INFO"))

class IPTVPlayer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IPTV Player - M3U")
        self.geometry("650x600")
        self.resizable(False, False)
        self.channels = []
        self.filtered_channels = []
        self.selected_index = None
        self.volume = 80

        # Search bar
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.search_entry = ctk.CTkEntry(self, placeholder_text="Search for a channel...", textvariable=self.search_var, width=450)
        self.search_entry.pack(pady=(20, 10))
        log("Search bar initialized", "DEBUG")

        # List
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.pack(pady=5, padx=20, fill="both", expand=True)
        self.listbox = ctk.CTkScrollableFrame(self.list_frame)
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
        log("Channel list initialized", "DEBUG")

        # Buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=10)
        self.load_btn = ctk.CTkButton(btn_frame, text="Open M3U", command=self.load_m3u, width=180)
        self.load_btn.grid(row=0, column=0, padx=10)
        self.play_btn = ctk.CTkButton(btn_frame, text="Play", command=self.play_selected_channel, width=180)
        self.play_btn.grid(row=0, column=1, padx=10)
        log("Buttons initialized", "DEBUG")

        # Volume slider
        volume_frame = ctk.CTkFrame(self)
        volume_frame.pack(pady=5, fill="x", padx=20)
        self.volume_label = ctk.CTkLabel(volume_frame, text=f"Volume: {self.volume}%")
        self.volume_label.pack(side="left", padx=10)
        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, number_of_steps=100, command=self.update_volume)
        self.volume_slider.set(self.volume)
        self.volume_slider.pack(side="left", fill="x", expand=True, padx=10)
        log("Volume slider initialized", "DEBUG")

        self.info_label = ctk.CTkLabel(self, text="No channels loaded", anchor="w")
        self.info_label.pack(padx=20, pady=5, fill="x")
        log("IPTV application started", "INFO")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- Search ---
    def on_search_change(self, *args):
        self.filter_channels(self.search_var.get())

    def filter_channels(self, text=""):
        self.update_list(text)

    # --- Channel widget ---
    def add_channel_widget(self, parent, name, index):
        frame = ctk.CTkFrame(parent, fg_color="transparent", height=40)
        frame.pack(fill="x", pady=2)
        btn = ctk.CTkButton(frame, text=name, fg_color="#1f1f1f", command=lambda i=index: self.select_channel(i))
        btn.pack(side="left", fill="x", expand=True, padx=5)
        return frame

    # --- Update list ---
    def update_list(self, search_text=""):
        for w in self.listbox.winfo_children():
            w.destroy()
        self.filtered_channels.clear()
        for idx, (name, url) in enumerate(self.channels):
            if search_text.lower() in name.lower():
                self.add_channel_widget(self.listbox, name, idx)
                self.filtered_channels.append((name, url))
        if not self.filtered_channels:
            lbl = ctk.CTkLabel(self.listbox, text="No channels found", text_color="gray")
            lbl.pack(pady=10)

    # --- Selection ---
    def select_channel(self, idx):
        self.selected_index = idx
        name, _ = self.channels[idx]
        log(f"Channel selected: {name}", "INFO")

    # --- Load M3U ---
    def load_m3u(self):
        filepath = filedialog.askopenfilename(filetypes=[("M3U Files", "*.m3u;*.m3u8")])
        log(f"Opening M3U dialog: {filepath}", "DEBUG")
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            self.channels.clear()
            name, count = None, 0
            for line in lines:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    name = line.split(",")[-1].strip()
                elif line and not line.startswith("#"):
                    url = line
                    self.channels.append((name if name else url, url))
                    count += 1
            self.info_label.configure(text=f"{count} channels loaded")
            log(f"{count} channels loaded from {os.path.basename(filepath)}", "INFO")
            self.update_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            log(f"M3U error: {e}", "ERROR")

    # --- Play ---
    def play_selected_channel(self):
        if self.selected_index is None or not self.channels:
            messagebox.showwarning("Warning", "Select a channel")
            log("Attempted playback without selection", "WARN")
            return
        name, url = self.channels[self.selected_index]
        self.play_channel_direct(name, url)

    def play_channel_direct(self, name, url):
        log(f"Playing channel: {name}", "INFO")
        log(f"URL: {url}", "DEBUG")
        self.info_label.configure(text=f"Loading {name}...")
        def run():
            try:
                if hasattr(self, 'ffplay_process') and self.ffplay_process.poll() is None:
                    self.ffplay_process.terminate()
                    self.ffplay_process.wait()
                cmd = [FFPLAY_PATH, "-autoexit", "-fs", "-volume", str(self.volume),
                       "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
                       "-analyzeduration", "2000000", "-probesize", "2000000", url]
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.ffplay_process = process
                self.after(1000, lambda: self.info_label.configure(text=f"Playing {name}"))
            except FileNotFoundError:
                messagebox.showerror("Error", f"ffplay not found ({FFPLAY_PATH})")
                log(f"ffplay not found ({FFPLAY_PATH})", "ERROR")
                self.info_label.configure(text="Error: ffplay not found")
            except Exception as e:
                messagebox.showerror("Error", f"Unable to launch ffplay\n{e}")
                log(f"Unable to launch ffplay: {e}", "ERROR")
                self.info_label.configure(text="Error during playback")
        threading.Thread(target=run, daemon=True).start()

    # --- Live volume control with pycaw ---
    def update_volume(self, value):
        new_volume = int(round(float(value)))
        if new_volume != self.volume:
            self.volume = new_volume
            self.volume_label.configure(text=f"Volume: {self.volume}%")
            log(f"Volume changed to {self.volume}%", "DEBUG")
            if hasattr(self, 'ffplay_process') and self.ffplay_process.poll() is None:
                try:
                    sessions = AudioUtilities.GetAllSessions()
                    for session in sessions:
                        if session.Process and "ffplay.exe" in session.Process.name().lower():
                            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                            volume.SetMasterVolume(self.volume / 100, None)
                except Exception as e:
                    log(f"Volume control error pycaw: {e}", "ERROR")

    # --- Close ---
    def on_close(self):
        log("Application close requested", "INFO")
        if hasattr(self, 'ffplay_process') and self.ffplay_process.poll() is None:
            self.ffplay_process.terminate()
            self.ffplay_process.wait()
        self.destroy()

if __name__ == "__main__":
    app = IPTVPlayer()
    app.mainloop()