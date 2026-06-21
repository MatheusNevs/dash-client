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

        self.sim_thread = None
        self.active_sims = {}  # sim_id -> data dict
        self.sim_frames = {}   # sim_id -> UI elements dict
        self.color_idx = 0

        self.setup_ui()

    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=250)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="Configurações", font=("Roboto", 20, "bold")).pack(pady=(20, 10))

        ctk.CTkLabel(self.sidebar, text="Número de Segmentos:").pack(anchor="w", padx=10)
        self.ent_segments = ctk.CTkEntry(self.sidebar)
        self.ent_segments.insert(0, "20")
        self.ent_segments.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(self.sidebar, text="Política ABR:").pack(anchor="w", padx=10)
        self.opt_policy = ctk.CTkOptionMenu(self.sidebar, values=["baseline", "buffer", "heuristic", "todas (simultâneas)"])
        self.opt_policy.set("heuristic")
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
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=(10, 0))
        self.main_frame.grid_rowconfigure(0, weight=3)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Dashboard Scrollable Area
        self.dashboard_scroll = ctk.CTkScrollableFrame(self.main_frame)
        self.dashboard_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Comparison Section (Top)
        self.comp_frame = ctk.CTkFrame(self.dashboard_scroll)
        self.comp_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(self.comp_frame, text="Gráficos Comparativos (Simulações Ativas)", font=("Roboto", 18, "bold")).pack(pady=5)
        
        self.comp_fig, (self.comp_ax1, self.comp_ax2) = plt.subplots(1, 2, figsize=(10, 4), facecolor='#2b2b2b')
        self.comp_fig.subplots_adjust(bottom=0.15)
        self.apply_plot_styles(self.comp_ax1, self.comp_ax2, "Comparativo: Bitrate Selecionado", "Comparativo: Nível do Buffer")
        
        self.comp_canvas = FigureCanvasTkAgg(self.comp_fig, master=self.comp_frame)
        self.comp_canvas.get_tk_widget().pack(fill="both", expand=True)

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

    def create_sim_row(self, sim_id, title):
        frame = ctk.CTkFrame(self.sims_container)
        frame.pack(fill="x", pady=10)
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text=title, font=("Roboto", 15, "bold"), text_color=self.active_sims[sim_id]["color"]).pack(side="left")
        
        btn_del = ctk.CTkButton(header, text="X Remover", width=60, fg_color="#b22222", hover_color="#8b0000", command=lambda: self.delete_sim(sim_id))
        btn_del.pack(side="right")
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5), facecolor='#2b2b2b')
        fig.subplots_adjust(bottom=0.15)
        self.apply_plot_styles(ax1, ax2, title1="Vazão vs Qualidade", title2="Nível do Buffer")
        
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.sim_frames[sim_id] = {
            "frame": frame,
            "fig": fig,
            "ax1": ax1,
            "ax2": ax2,
            "canvas": canvas
        }

    def delete_sim(self, sim_id):
        if sim_id in self.active_sims:
            del self.active_sims[sim_id]
        if sim_id in self.sim_frames:
            self.sim_frames[sim_id]["frame"].destroy()
            del self.sim_frames[sim_id]
        self.update_comparison_plot()
        self.log(f"--- Simulação {sim_id[:4]} removida ---")

    def _update_gui(self, sim_id, metric_data):
        sim = self.active_sims.get(sim_id)
        if not sim:
            return
            
        sim["segments"].append(metric_data["segment"])
        sim["vazao"].append(metric_data["vazão_kbps"])
        sim["bitrate"].append(metric_data["bitrate_kbps"])
        sim["buffer"].append(metric_data["buffer_level_s"])

        # Update Individual Row
        ui = self.sim_frames.get(sim_id)
        if ui:
            ui["ax1"].clear()
            ui["ax2"].clear()
            self.apply_plot_styles(ui["ax1"], ui["ax2"], "Vazão vs Qualidade", "Nível do Buffer")
            
            ui["ax1"].plot(sim["segments"], sim["vazao"], color='tab:blue', linestyle='--', marker='o', label='Vazão', alpha=0.6)
            ui["ax1"].step(sim["segments"], sim["bitrate"], color='tab:red', where='post', label='Bitrate', linewidth=2)
            ui["ax1"].legend(loc="upper left", facecolor='#2b2b2b', labelcolor='white')
            
            ui["ax2"].plot(sim["segments"], sim["buffer"], color='green', linewidth=2)
            ui["ax2"].axhline(y=2.0, color='r', linestyle='--', alpha=0.5)
            
            ui["canvas"].draw()

        self.update_comparison_plot()

        q = metric_data['quality']
        t = metric_data['vazão_kbps']
        b = metric_data['buffer_level_s']
        s = metric_data['segment']
        log_line = f"[{sim['name'][:15]}...] Seg {s:03d} | Qualidade: {q:5} | Vazão: {t:7.2f} kbps | Buffer: {b:5.2f}s"
        self.log(log_line)

    def update_comparison_plot(self):
        self.comp_ax1.clear()
        self.comp_ax2.clear()
        self.apply_plot_styles(self.comp_ax1, self.comp_ax2, "Comparativo: Bitrate Selecionado", "Comparativo: Nível do Buffer")
        
        has_data = False
        for sim_id, sim in self.active_sims.items():
            if not sim["segments"]: continue
            has_data = True
            color = sim["color"]
            label = sim["name"]
            
            self.comp_ax1.step(sim["segments"], sim["bitrate"], color=color, where='post', linewidth=2, label=label)
            self.comp_ax2.plot(sim["segments"], sim["buffer"], color=color, linewidth=2, label=label)
            
        if has_data:
            self.comp_ax1.legend(loc="upper left", facecolor='#2b2b2b', labelcolor='white', fontsize=9)
            self.comp_ax2.legend(loc="upper left", facecolor='#2b2b2b', labelcolor='white', fontsize=9)
            
        self.comp_ax2.axhline(y=2.0, color='r', linestyle='--', alpha=0.5)
        self.comp_canvas.draw()

    def _run_in_thread(self, policy_mode, num_segments, params, sim_ids_map):
        def update_cb(p_name, metric_data):
            sim_id = sim_ids_map.get(p_name)
            if sim_id:
                self.after(0, self._update_gui, sim_id, metric_data)

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
        
        sim_ids_map = {}
        
        if policy == "todas (simultâneas)":
            policy_mode = "all_simultaneous"
            for p in ["baseline", "buffer", "heuristic"]:
                sim_id = str(uuid.uuid4())
                sim_ids_map[p] = sim_id
                name = f"Heurística SIMULTÂNEA (sf={params['safety_factor']})" if p == "heuristic" else f"{p.capitalize()} SIMULTÂNEA (sf={params['safety_factor']})"
                color = COLORS[self.color_idx % len(COLORS)]
                self.color_idx += 1
                self.active_sims[sim_id] = {"name": name, "color": color, "segments": [], "vazao": [], "bitrate": [], "buffer": []}
                self.create_sim_row(sim_id, title=name)
            self.log(f"\n--- INICIANDO SIMULAÇÃO EM LOTE SOBRE A MESMA VAZÃO ---")
        else:
            policy_mode = policy
            sim_id = str(uuid.uuid4())
            sim_ids_map[policy] = sim_id
            name = f"Heurística (α={params['alpha']}, γ={params['gamma']}, sf={params['safety_factor']})" if policy == "heuristic" else f"{policy.capitalize()} (sf={params['safety_factor']})"
            color = COLORS[self.color_idx % len(COLORS)]
            self.color_idx += 1
            self.active_sims[sim_id] = {"name": name, "color": color, "segments": [], "vazao": [], "bitrate": [], "buffer": []}
            self.create_sim_row(sim_id, title=name)
            self.log(f"\n--- INICIANDO SIMULAÇÃO [{name}] ---")

        threading.Thread(target=self._run_in_thread, args=(policy_mode, num_segments, params, sim_ids_map), daemon=True).start()

if __name__ == "__main__":
    app = DASHFrontend()
    app.mainloop()
