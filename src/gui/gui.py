import tkinter as tk
from tkinter import ttk
import threading
import sys
import time

from src.core.storage_service import StorageService


class GUIOutputStream:
    """
    Stream personalizado que redirige stdout a la GUI en tiempo real.
    Usa una cola thread-safe para comunicarse con el hilo principal.
    """
    
    def __init__(self, gui_callback, root):
        self.gui_callback = gui_callback
        self.root = root
        self.buffer = ""
    
    def write(self, text: str):
        """Escribe texto al log de la GUI."""
        if text.strip() != "":
            # Acumular en buffer hasta encontrar newline
            now = time.strftime("%H:%M:%S")
            text = f"[{now}] {text}\n"
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                if line.strip():  # Solo si hay contenido
                    # Usar after() para actualizar desde el hilo principal
                    self.root.after(0, lambda l=line: self.gui_callback(l))
    
    def flush(self):
        """Flush del buffer."""
        if self.buffer.strip():
            self.root.after(0, lambda l=self.buffer: self.gui_callback(l))
            self.buffer = ""

class Colors:
    """Paleta de colores para el tema oscuro."""
    BG_DARK = "#1e1e1e"
    BG_MEDIUM = "#252526"
    BG_LIGHT = "#2d2d30"
    FG_PRIMARY = "#d4d4d4"
    FG_SECONDARY = "#808080"
    ACCENT = "#0e639c"
    ACCENT_HOVER = "#1177bb"
    
    # Colores para mensajes
    INFO = "#3794ff"
    SUCCESS = "#4ec9b0"
    WARNING = "#dcdcaa"
    ERROR = "#f14c4c"
    HEADER = "#FFFFFF"
    FILE = "#64b5f6"


# Lista de depósitos disponibles
AVAILABLE_DEPOTS = ["PERI", "SIGNIA"]

class MaxStorageGUI:
    """Interfaz gráfica para Max Storage Andina."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Max Storage Andina")
        self.root.geometry("800x550")
        self.root.resizable(True, True)
        self.root.configure(bg=Colors.BG_DARK)
        
        self._is_running = False
        self._selected_depot = tk.StringVar(value=AVAILABLE_DEPOTS[0])
        self._setup_styles()
        self._setup_ui()
    
    def _setup_styles(self):
        """Configura los estilos del tema oscuro."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Frame
        style.configure(
            "Dark.TFrame",
            background=Colors.BG_DARK
        )
        
        # Label
        style.configure(
            "Dark.TLabel",
            background=Colors.BG_DARK,
            foreground=Colors.FG_PRIMARY,
            font=("Segoe UI", 10)
        )
        
        style.configure(
            "Title.TLabel",
            background=Colors.BG_DARK,
            foreground=Colors.FG_PRIMARY,
            font=("Segoe UI", 16, "bold")
        )
        
        style.configure(
            "Status.TLabel",
            background=Colors.BG_MEDIUM,
            foreground=Colors.FG_SECONDARY,
            font=("Segoe UI", 9)
        )
        
        # Button
        style.configure(
            "Accent.TButton",
            background=Colors.ACCENT,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(15, 8)
        )
        style.map(
            "Accent.TButton",
            background=[("active", Colors.ACCENT_HOVER), ("disabled", Colors.BG_LIGHT)]
        )
        
        style.configure(
            "Secondary.TButton",
            background=Colors.BG_LIGHT,
            foreground=Colors.FG_PRIMARY,
            font=("Segoe UI", 10),
            padding=(15, 8)
        )
        style.map(
            "Secondary.TButton",
            background=[("active", Colors.BG_MEDIUM)]
        )
        
        # Combobox
        style.configure(
            "Dark.TCombobox",
            fieldbackground=Colors.BG_LIGHT,
            background=Colors.BG_LIGHT,
            foreground=Colors.FG_PRIMARY,
            arrowcolor=Colors.FG_PRIMARY,
            font=("Segoe UI", 10)
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", Colors.BG_LIGHT)],
            selectbackground=[("readonly", Colors.ACCENT)],
            selectforeground=[("readonly", "white")]
        )
        
        # Configurar el dropdown del combobox
        self.root.option_add("*TCombobox*Listbox.background", Colors.BG_LIGHT)
        self.root.option_add("*TCombobox*Listbox.foreground", Colors.FG_PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectBackground", Colors.ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))
    
    def _setup_ui(self):
        """Configura los elementos de la interfaz."""
        # Frame principal
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(
            main_frame,
            text="Max Storage Andina",
            style="Title.TLabel"
        )
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Frame de controles (selector + botones)
        controls_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        controls_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Frame para selector de depósito
        depot_frame = ttk.Frame(controls_frame, style="Dark.TFrame")
        depot_frame.pack(side=tk.LEFT, padx=(0, 20))
        
        depot_label = ttk.Label(
            depot_frame,
            text="Depósito:",
            style="Dark.TLabel"
        )
        depot_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.depot_combo = ttk.Combobox(
            depot_frame,
            textvariable=self._selected_depot,
            values=AVAILABLE_DEPOTS,
            state="readonly",
            style="Dark.TCombobox",
            width=15
        )
        self.depot_combo.pack(side=tk.LEFT)
        
        # Frame de botones
        button_frame = ttk.Frame(controls_frame, style="Dark.TFrame")
        button_frame.pack(side=tk.LEFT)
        
        # Botón para procesar reportes
        self.btn_process = ttk.Button(
            button_frame, 
            text="▶  Procesar Reportes",
            style="Accent.TButton",
            command=self._run_processing
        )
        self.btn_process.pack(side=tk.LEFT, padx=(0, 10))
        
        # Botón para limpiar log
        self.btn_clear = ttk.Button(
            button_frame,
            text="🗑  Limpiar",
            style="Secondary.TButton",
            command=self._clear_log
        )
        self.btn_clear.pack(side=tk.LEFT, padx=(0, 10))
        
        # Indicador de progreso
        self.progress_label = ttk.Label(
            button_frame, 
            text="",
            style="Dark.TLabel"
        )
        self.progress_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Label para consola
        log_label = ttk.Label(
            main_frame, 
            text="Consola",
            style="Dark.TLabel"
        )
        log_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Frame para el área de texto (con borde)
        text_frame = tk.Frame(main_frame, bg=Colors.BG_LIGHT, padx=2, pady=2)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Área de texto con scroll para logs
        self.log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Cascadia Code", 10),
            bg=Colors.BG_MEDIUM,
            fg=Colors.FG_PRIMARY,
            insertbackground=Colors.FG_PRIMARY,
            selectbackground=Colors.ACCENT,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        
        # Scrollbar personalizada
        scrollbar = ttk.Scrollbar(text_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # Configurar tags para colores de mensajes
        self.log_text.tag_configure("info", foreground=Colors.INFO)
        self.log_text.tag_configure("success", foreground=Colors.SUCCESS)
        self.log_text.tag_configure("warning", foreground=Colors.WARNING)
        self.log_text.tag_configure("error", foreground=Colors.ERROR)
        self.log_text.tag_configure("header", foreground=Colors.HEADER)
        self.log_text.tag_configure("file", foreground=Colors.FILE)
        self.log_text.tag_configure("normal", foreground=Colors.FG_PRIMARY)
        
        # Barra de estado
        self.status_bar = ttk.Label(
            self.root, 
            text="  Listo", 
            style="Status.TLabel",
            anchor=tk.W,
            padding=(5, 3)
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
    
    def _log(self, message: str, tag: str = "normal"):
        """Agrega un mensaje al área de log con color."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def _clear_log(self):
        """Limpia el área de log."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _set_running(self, running: bool):
        """Actualiza el estado de ejecución."""
        self._is_running = running
        state = tk.DISABLED if running else tk.NORMAL
        self.btn_process.config(state=state)
        combo_state = "disabled" if running else "readonly"
        self.depot_combo.config(state=combo_state)
        
        if running:
            self.progress_label.config(text="⏳ Procesando...")
            self.status_bar.config(text="  Procesando reportes...")
        else:
            self.progress_label.config(text="")
            self.status_bar.config(text="  Listo")
    
    def _run_processing(self):
        """Ejecuta el procesamiento en un hilo separado."""
        if self._is_running:
            return
        
        self._set_running(True)
        thread = threading.Thread(target=self._process_reports, daemon=True)
        thread.start()
    
    def _log_stdout(self, message: str):
        """Callback para logs desde stdout redirigido."""
        if "Processing file:" in message:
            self._log(message, "file")
        elif "Error" in message or "ERROR" in message:
            self._log(message, "error")
        elif "Warning" in message or "WARNING" in message:
            self._log(message, "warning")
        else:
            self._log(message, "normal")
    
    def _process_reports(self):
        """Procesa los reportes y muestra resultados."""
        depot_name = self._selected_depot.get()
        
        try:
            self._log("═" * 55, "header")
            self._log(f"  INICIANDO PROCESAMIENTO - Depósito: {depot_name}", "header")
            self._log("═" * 55, "header")
            
            service = StorageService()
            
            # Redirigir stdout para mostrar prints en tiempo real
            old_stdout = sys.stdout
            sys.stdout = GUIOutputStream(self._log_stdout, self.root)
            
            try:
                result = service.process_all(depot_name)
            finally:
                sys.stdout.flush()
                sys.stdout = old_stdout
            
            # Guardar resultados
            self._log("\n💾 Guardando resultados...", "info")
            service.save_results(result, depot_name)
            
            # Mostrar resumen
            self._log("\n" + "═" * 55, "header")
            self._log("  RESUMEN", "header")
            self._log("═" * 55, "header")
            
            self._log(f"📁 Archivos procesados: {len(result.processed_files)}", "success")
            
            if result.skipped_files:
                self._log(f"⏭️  Archivos saltados: {len(result.skipped_files)}", "warning")
                for f in result.skipped_files[:5]:
                    self._log(f"    • {f}", "warning")
                if len(result.skipped_files) > 5:
                    self._log(f"    ... y {len(result.skipped_files) - 5} más", "warning")
            
            error_count = len(result.error_protocols['PROTOCOL'].unique()) if not result.error_protocols.empty else 0
            if error_count > 0:
                self._log(f"⚠️  Protocolos con errores: {error_count}", "error")
            else:
                self._log(f"✓  Sin errores de protocolo", "success")
            
            max_count = len(result.max_values['PROTOCOL'].unique()) if not result.max_values.empty else 0
            self._log(f"📊 Protocolos calculados: {max_count}", "info")
            
            self._log("\n✅ Procesamiento completado exitosamente!", "success")
            self._log("═" * 55, "header")
            
        except Exception as e:
            self._log(f"\n❌ ERROR: {str(e)}", "error")
            self._log("═" * 55, "header")
        finally:
            self.root.after(0, lambda: self._set_running(False))
    
    def run(self):
        """Inicia la aplicación."""
        self.root.mainloop()


def main():
    """Punto de entrada para la interfaz gráfica."""
    app = MaxStorageGUI()
    app.run()


if __name__ == "__main__":
    main()
