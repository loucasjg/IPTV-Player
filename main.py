import customtkinter as ctk
from tkinter import filedialog, messagebox
import subprocess
import threading
import datetime
import os
import atexit

# --- Nouveauté pour le volume ---
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

# --- CONFIG ---
FFPLAY_PATH = "ffplay"  # si ffplay est dans PATH
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

atexit.register(lambda: log("Application fermée", "INFO"))

class IPTVPlayer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Lecteur IPTV - M3U")
        self.geometry("650x600")
        self.resizable(False, False)

        self.channels = []
        self.filtered_channels = []
        self.selected_index = None
        self.volume = 80

        # Barre recherche
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.search_entry = ctk.CTkEntry(self, placeholder_text="Rechercher une chaîne...", textvariable=self.search_var, width=450)
        self.search_entry.pack(pady=(20,10))
        log("Barre de recherche initialisée", "DEBUG")

        # Liste
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.pack(pady=5, padx=20, fill="both", expand=True)
        self.listbox = ctk.CTkScrollableFrame(self.list_frame)
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
        log("Liste des chaînes initialisée", "DEBUG")

        # Boutons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=10)
        self.load_btn = ctk.CTkButton(btn_frame, text="Ouvrir M3U", command=self.load_m3u, width=180)
        self.load_btn.grid(row=0, column=0, padx=10)
        self.play_btn = ctk.CTkButton(btn_frame, text="Lire", command=self.play_selected_channel, width=180)
        self.play_btn.grid(row=0, column=1, padx=10)
        log("Boutons initialisés", "DEBUG")

        # Slider volume
        volume_frame = ctk.CTkFrame(self)
        volume_frame.pack(pady=5, fill="x", padx=20)
        self.volume_label = ctk.CTkLabel(volume_frame, text=f"Volume : {self.volume}%")
        self.volume_label.pack(side="left", padx=10)
        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, number_of_steps=100, command=self.update_volume)
        self.volume_slider.set(self.volume)
        self.volume_slider.pack(side="left", fill="x", expand=True, padx=10)
        log("Slider volume initialisé", "DEBUG")

        self.info_label = ctk.CTkLabel(self, text="Aucune chaîne chargée", anchor="w")
        self.info_label.pack(padx=20, pady=5, fill="x")
        log("Application IPTV démarrée", "INFO")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- Recherche ---
    def on_search_change(self, *args):
        self.filter_channels(self.search_var.get())

    def filter_channels(self, text=""):
        self.update_list(text)

    # --- Widget chaîne ---
    def add_channel_widget(self, parent, name, index):
        frame = ctk.CTkFrame(parent, fg_color="transparent", height=40)
        frame.pack(fill="x", pady=2)
        btn = ctk.CTkButton(frame, text=name, fg_color="#1f1f1f", command=lambda i=index: self.select_channel(i))
        btn.pack(side="left", fill="x", expand=True, padx=5)
        return frame

    # --- Mettre à jour liste ---
    def update_list(self, search_text=""):
        for w in self.listbox.winfo_children():
            w.destroy()
        self.filtered_channels.clear()
        for idx, (name, url) in enumerate(self.channels):
            if search_text.lower() in name.lower():
                self.add_channel_widget(self.listbox, name, idx)
                self.filtered_channels.append((name, url))
        if not self.filtered_channels:
            lbl = ctk.CTkLabel(self.listbox, text="Aucune chaîne trouvée", text_color="gray")
            lbl.pack(pady=10)

    # --- Sélection ---
    def select_channel(self, idx):
        self.selected_index = idx
        name, _ = self.channels[idx]
        log(f"Chaîne sélectionnée : {name}", "INFO")

    # --- Charger M3U ---
    def load_m3u(self):
        filepath = filedialog.askopenfilename(filetypes=[("M3U Files", "*.m3u;*.m3u8")])
        log(f"Ouverture boîte de dialogue M3U : {filepath}", "DEBUG")
        if not filepath: return
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
            self.info_label.configure(text=f"{count} chaînes chargées")
            log(f"{count} chaînes chargées depuis {os.path.basename(filepath)}", "INFO")
            self.update_list()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            log(f"Erreur M3U : {e}", "ERROR")

    # --- Jouer ---
    def play_selected_channel(self):
        if self.selected_index is None or not self.channels:
            messagebox.showwarning("Attention", "Sélectionne une chaîne")
            log("Tentative lecture sans sélection", "WARN")
            return
        name, url = self.channels[self.selected_index]
        self.play_channel_direct(name, url)

    def play_channel_direct(self, name, url):
        log(f"Lecture de la chaîne : {name}", "INFO")
        log(f"URL : {url}", "DEBUG")
        self.info_label.configure(text=f"Chargement de {name}...")

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
                self.after(1000, lambda: self.info_label.configure(text=f"Lecture de {name}"))
            except FileNotFoundError:
                messagebox.showerror("Erreur", f"ffplay introuvable ({FFPLAY_PATH})")
                log(f"ffplay introuvable ({FFPLAY_PATH})", "ERROR")
                self.info_label.configure(text="Erreur : ffplay introuvable")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de lancer ffplay\n{e}")
                log(f"Impossible de lancer ffplay : {e}", "ERROR")
                self.info_label.configure(text="Erreur lors de la lecture")

        threading.Thread(target=run, daemon=True).start()

    # --- Volume en live avec pycaw ---
    def update_volume(self, value):
        new_volume = int(round(float(value)))
        if new_volume != self.volume:
            self.volume = new_volume
            self.volume_label.configure(text=f"Volume : {self.volume}%")
            log(f"Volume changé à {self.volume}%", "DEBUG")
            if hasattr(self, 'ffplay_process') and self.ffplay_process.poll() is None:
                try:
                    sessions = AudioUtilities.GetAllSessions()
                    for session in sessions:
                        if session.Process and "ffplay.exe" in session.Process.name().lower():
                            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                            volume.SetMasterVolume(self.volume / 100, None)
                except Exception as e:
                    log(f"Erreur contrôle volume pycaw: {e}", "ERROR")

    # --- Fermeture ---
    def on_close(self):
        log("Fermeture application demandée", "INFO")
        if hasattr(self, 'ffplay_process') and self.ffplay_process.poll() is None:
            self.ffplay_process.terminate()
            self.ffplay_process.wait()
        self.destroy()

if __name__ == "__main__":
    app = IPTVPlayer()
    app.mainloop()
