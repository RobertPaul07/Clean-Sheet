"""Interfaccia grafica con Tkinter (incluso in Python per Windows, nessuna installazione extra).

La pulizia gira in un thread separato: con file grandi la finestra non si blocca.
Tkinter però va aggiornato solo dal thread principale, per questo usiamo root.after().
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .cleaning import Options, clean_files
from .file_io import load_file, save_result

OPTION_LABELS = {
    "trim_spaces": "Rimuovi spazi superflui",
    "drop_empty": "Rimuovi righe e colonne vuote",
    "check_emails": "Controlla e normalizza le email",
    "normalize_phones": "Normalizza i telefoni (+39...)",
    "remove_duplicates": "Rimuovi i duplicati esatti",
    "flag_similar": "Segnala i possibili duplicati",
}


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.files: list[str] = []
        root.title(f"CleanSheet {__version__}")
        root.minsize(560, 520)

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        # --- file
        ttk.Label(main, text="1. Scegli i file (CSV o Excel)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.listbox = tk.Listbox(main, height=6, selectmode="extended")
        self.listbox.pack(fill="x", pady=(4, 4))
        buttons = ttk.Frame(main)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Aggiungi file…", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="Rimuovi selezionati", command=self.remove_selected).pack(side="left", padx=6)

        # --- opzioni
        ttk.Label(main, text="2. Cosa fare", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 0))
        self.option_vars = {key: tk.BooleanVar(value=True) for key in OPTION_LABELS}
        for key, label in OPTION_LABELS.items():
            ttk.Checkbutton(main, text=label, variable=self.option_vars[key]).pack(anchor="w")

        # --- avvio
        ttk.Label(main, text="3. Avvia", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 0))
        self.run_button = ttk.Button(main, text="Pulisci e salva…", command=self.run)
        self.run_button.pack(anchor="w", pady=4)
        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill="x")

        # --- riepilogo
        self.output = tk.Text(main, height=10, state="disabled", wrap="word")
        self.output.pack(fill="both", expand=True, pady=(8, 0))

    # ------------------------------------------------------------ azioni

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Scegli i file",
            filetypes=[("CSV o Excel", "*.csv *.txt *.xlsx *.xlsm"), ("Tutti i file", "*.*")],
        )
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.listbox.insert("end", Path(p).name)

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.files[i]

    def run(self):
        if not self.files:
            messagebox.showwarning("Nessun file", "Aggiungi almeno un file.")
            return
        default_name = Path(self.files[0]).stem + "_pulito.xlsx"
        out_path = filedialog.asksaveasfilename(
            title="Salva il risultato", defaultextension=".xlsx",
            initialfile=default_name, filetypes=[("Excel", "*.xlsx")],
        )
        if not out_path:
            return

        options = Options(**{k: v.get() for k, v in self.option_vars.items()})
        self.run_button.state(["disabled"])
        self.progress.start(10)
        self.show("Elaborazione in corso…")
        threading.Thread(target=self._work, args=(list(self.files), out_path, options), daemon=True).start()

    def _work(self, files, out_path, options):
        """Gira nel thread secondario: niente chiamate dirette a Tkinter qui."""
        try:
            frames = [load_file(f) for f in files]
            result = clean_files(frames, options)
            save_result(out_path, result.data, result.issues, result.summary)
            text = "\n".join(result.summary) + f"\n\nSalvato in:\n{out_path}"
            self.root.after(0, self._done, text, None)
        except PermissionError:
            self.root.after(0, self._done, None, "Impossibile salvare: il file è aperto in Excel? Chiudilo e riprova.")
        except Exception as e:  # mostriamo l'errore invece di far crashare il programma
            self.root.after(0, self._done, None, f"{type(e).__name__}: {e}")

    def _done(self, text, error):
        self.progress.stop()
        self.run_button.state(["!disabled"])
        if error:
            self.show("Errore:\n" + error)
            messagebox.showerror("Errore", error)
        else:
            self.show(text)

    def show(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
