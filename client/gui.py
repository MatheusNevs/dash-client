import os
import sys
import threading
import uuid
import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib

matplotlib.use('TkAgg')
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#17becf', 
    '#8c564b', '#e377c2', '#bcbd22', '#d62728', '#7f7f7f'
]

class DASHFrontend(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DASH Adaptive Streaming Client - Live Benchmarking")
        self.geometry("1400x900")

        self.active_runs = {}  # run_id -> dict
        self.run_frames = {}   # run_id -> UI elements dict
        self.color_idx = 0

        self.setup_ui()

    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=250)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="Configurações", font=("Roboto", 20, "bold")).pack(pady=(20, 10))

        ctk.CTkLabel(self.sidebar, text="Número de Segmentos:").pack(anchor="w", padx=10)
        self.ent_segments = ctk.CTkEntry(self.sidebar)
        self.ent_segments.insert(0, "20")
        self.ent_segments.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.sidebar, text="Política ABR:").pack(anchor="w", padx=10)
        self.opt_policy = ctk.CTkOptionMenu(self.sidebar, values=["baseline", "buffer", "heuristic", "todas (simultâneas)"])
        self.opt_policy.set("todas (simultâneas)")
        self.opt_policy.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.sidebar, text="Safety Factor (0.0 - 1.0):").pack(anchor="w", padx=10)
        self.ent_sf = ctk.CTkEntry(self.sidebar)
        self.ent_sf.insert(0, "0.92")
        self.ent_sf.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.sidebar, text="Alpha (Vazão EWMA):").pack(anchor="w", padx=10)
        self.ent_alpha = ctk.CTkEntry(self.sidebar)
        self.ent_alpha.insert(0, "0.3")
        self.ent_alpha.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.sidebar, text="Beta (Jitter EWMA):").pack(anchor="w", padx=10)
        self.ent_beta = ctk.CTkEntry(self.sidebar)
        self.ent_beta.insert(0, "0.3")
        self.ent_beta.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.sidebar, text="Gamma (Penalidade):").pack(anchor="w", padx=10)
        self.ent_gamma = ctk.CTkEntry(self.sidebar)
        self.ent_gamma.insert(0, "1.5")
        self.ent_gamma.pack(fill="x", padx=10, pady=(0, 20))

        self.btn_start = ctk.CTkButton(self.sidebar, text="Iniciar Nova Simulação", command=self.start_simulation)
        self.btn_start.pack(fill="x", padx=10, pady=10)

        # --- Main Area ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.main_frame.grid_rowconfigure(0, weight=3)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Dashboard Scrollable Area
        self.dashboard_scroll = ctk.CTkScrollableFrame(self.main_frame)
        self.dashboard_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Container for Individual Simulation Rows
        self.sims_container = ctk.CTkFrame(self.dashboard_scroll, fg_color="transparent")
        self.sims_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Logs Frame
        self.log_frame = ctk.CTkFrame(self.main_frame)
        self.log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        self.log_box = ctk.CTkTextbox(self.log_frame, font=("Courier", 12))
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)

    def apply_plot_styles(self, ax1, ax2, title1, title2):
        for ax in (ax1, ax2):
            ax.set_facecolor('#2b2b2b')
            ax.tick_params(colors='white')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.title.set_color('white')
            for spine in ax.spines.values():
                spine.set_color('gray')
            ax.grid(True, alpha=0.3, color='gray')

        ax1.set_title(title1)
        ax1.set_xlabel("Segmento")
        ax1.set_ylabel("kbps")
        
        ax2.set_title(title2)
        ax2.set_xlabel("Segmento")
        ax2.set_ylabel("Segundos")

    def log(self, text):
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")

    def create_run_row(self, run_id, title):
        frame = ctk.CTkFrame(self.sims_container)
        frame.pack(fill="x", pady=10)
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text=title, font=("Roboto", 15, "bold")).pack(side="left")
        
        btn_del = ctk.CTkButton(header, text="X Remover", width=60, fg_color="#b22222", hover_color="#8b0000", command=lambda: self.delete_run(run_id))
        btn_del.pack(side="right")
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5), facecolor='#2b2b2b')
        fig.subplots_adjust(bottom=0.15)
        self.apply_plot_styles(ax1, ax2, title1="Vazão vs Qualidade", title2="Nível do Buffer")
        
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.run_frames[run_id] = {
            "frame": frame,
            "fig": fig,
            "ax1": ax1,
            "ax2": ax2,
            "canvas": canvas
        }

    def delete_run(self, run_id):
        if run_id in self.active_runs:
            del self.active_runs[run_id]
        if run_id in self.run_frames:
            self.run_frames[run_id]["frame"].destroy()
            del self.run_frames[run_id]
        self.log(f"--- Simulação removida ---")

    def _update_gui(self, run_id, p_name, metric_data):
        run = self.active_runs.get(run_id)
        if not run: return
        p_data = run["policies"].get(p_name)
        if not p_data: return
        
        p_data["segments"].append(metric_data["segment"])
        p_data["vazao"].append(metric_data["vazão_kbps"])
        p_data["bitrate"].append(metric_data["bitrate_kbps"])
        p_data["buffer"].append(metric_data["buffer_level_s"])
        p_data["failover"].append(metric_data["failover_total"])

        ui = self.run_frames.get(run_id)
        if ui:
            ui["ax1"].clear()
            ui["ax2"].clear()
            self.apply_plot_styles(ui["ax1"], ui["ax2"], "Vazão vs Qualidade", "Nível do Buffer")
            
            vazao_plotted = False
            for name, data in run["policies"].items():
                if not data["segments"]: continue
                
                if not vazao_plotted:
                    ui["ax1"].plot(data["segments"], data["vazao"], color='white', linestyle='--', marker='o', label='Vazão da Rede', alpha=0.3)
                    vazao_plotted = True
                    
                ui["ax1"].step(data["segments"], data["bitrate"], color=data["color"], where='post', label=f'Bitrate ({name})', linewidth=2)
                ui["ax2"].plot(data["segments"], data["buffer"], color=data["color"], label=f'Buffer ({name})', linewidth=2)
                
                # Failovers
                for idx, f_total in enumerate(data["failover"]):
                    if idx > 0 and f_total > data["failover"][idx-1]:
                        # Draw failover line only once per segment across all policies
                        if name == list(run["policies"].keys())[0]:
                            ui["ax1"].axvline(x=data["segments"][idx], color='red', linestyle=':', alpha=0.8, linewidth=2, label='Failover' if f_total==1 else "")
                            ui["ax2"].axvline(x=data["segments"][idx], color='red', linestyle=':', alpha=0.8, linewidth=2)

            ui["ax1"].legend(loc="upper left", facecolor='#2b2b2b', labelcolor='white', fontsize=9)
            ui["ax2"].legend(loc="upper left", facecolor='#2b2b2b', labelcolor='white', fontsize=9)
            ui["ax2"].axhline(y=2.0, color='r', linestyle='--', alpha=0.5)
            ui["ax2"].axhline(y=30.0, color='cyan', linestyle=':', alpha=0.5, label='Max Buffer')
            ui["canvas"].draw()

        q = metric_data['quality']
        t = metric_data['vazão_kbps']
        b = metric_data['buffer_level_s']
        s = metric_data['segment']
        log_line = f"[{p_name.upper()[:3]}] Seg {s:03d} | Qual:{q:5} | Vazão:{t:7.2f} | Buf:{b:5.2f}s | Failovers:{metric_data['failover_total']}"
        self.log(log_line)

    def _run_in_thread(self, policy_mode, num_segments, params, run_id):
        def update_cb(p_name, metric_data):
            self.after(0, self._update_gui, run_id, p_name, metric_data)

        try:
            from simulator import run_simulation
            run_simulation(num_segments, policy_mode, gui_params=params, update_callback=update_cb)
            self.after(0, self.log, "\n--- SIMULAÇÃO FINALIZADA ---")
        except Exception as e:
            self.after(0, self.log, f"\nERRO NA SIMULAÇÃO: {str(e)}")
        finally:
            self.after(0, lambda: self.btn_start.configure(state="normal"))

    def start_simulation(self):
        try:
            num_segments = int(self.ent_segments.get())
            policy = self.opt_policy.get()
            params = {
                "safety_factor": float(self.ent_sf.get()),
                "alpha": float(self.ent_alpha.get()),
                "beta": float(self.ent_beta.get()),
                "gamma": float(self.ent_gamma.get())
            }
        except ValueError:
            self.log("ERRO: Verifique se os parâmetros numéricos estão corretos.")
            return

        self.btn_start.configure(state="disabled")
        
        run_id = str(uuid.uuid4())
        
        if policy == "todas (simultâneas)":
            policy_mode = "all_simultaneous"
            title = f"Simulação Simultânea (Lote) - Segmentos: {num_segments}"
            self.active_runs[run_id] = {"title": title, "policies": {}}
            for i, p in enumerate(["baseline", "buffer", "heuristic"]):
                self.active_runs[run_id]["policies"][p] = {
                    "color": COLORS[i % len(COLORS)],
                    "segments": [], "vazao": [], "bitrate": [], "buffer": [], "failover": []
                }
            self.log(f"\n--- INICIANDO LOTE SIMULTÂNEO ---")
        else:
            policy_mode = policy
            title = f"Simulação Única ({policy.capitalize()}) - Segmentos: {num_segments}"
            self.active_runs[run_id] = {"title": title, "policies": {}}
            self.active_runs[run_id]["policies"][policy] = {
                "color": COLORS[self.color_idx % len(COLORS)],
                "segments": [], "vazao": [], "bitrate": [], "buffer": [], "failover": []
            }
            self.color_idx += 1
            self.log(f"\n--- INICIANDO SIMULAÇÃO [{policy}] ---")

        self.create_run_row(run_id, title)
        threading.Thread(target=self._run_in_thread, args=(policy_mode, num_segments, params, run_id), daemon=True).start()

if __name__ == "__main__":
    app = DASHFrontend()
    app.mainloop()
