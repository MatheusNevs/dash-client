"""
Módulo Principal de Execução do Cliente DASH ABR.

Este arquivo atua como o ponto de entrada (entry point) da aplicação, permitindo
iniciar o cliente de streaming via linha de comando (CLI) ou através da interface
gráfica interativa (GUI).
"""

import sys
import os
import argparse

# Adiciona o diretório atual ao sys.path para garantir a resolução correta de importações relativas
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from simulator import run_simulation

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente e Simulador de Streaming Adaptativo DASH")
    parser.add_argument("-n", "--segments", type=int, default=20, help="Número de segmentos a serem baixados")
    parser.add_argument(
        "-p", "--policy",
        type=str,
        choices=["baseline", "buffer", "heuristic", "all", "all_simultaneous"],
        default="baseline",
        help="Política de ABR a ser utilizada"
    )
    parser.add_argument("-g", "--generate", action="store_true", help="Gera gráficos comparativos automaticamente ao finalizar")
    parser.add_argument("--gui", action="store_true", help="Inicia a interface gráfica Desktop (CustomTkinter)")
    
    args = parser.parse_args()
    
    # Inicialização do modo Interface Gráfica (GUI)
    if args.gui:
        try:
            from gui import DASHFrontend
            app = DASHFrontend()
            app.mainloop()
            sys.exit(0)
        except ImportError as e:
            print(f"Erro ao carregar a interface gráfica: {e}")
            sys.exit(1)

    # Execução via Linha de Comando (CLI)
    if args.policy in ["all", "all_simultaneous"]:
        print(f"\nExecutando simulação simultânea para todas as políticas (mesmo trace de rede)...")
        run_simulation(args.segments, "all_simultaneous")
    else:
        run_simulation(args.segments, args.policy)

    # Geração automática de gráficos se solicitada via flag -g
    if args.generate:
        print("\nGerando gráficos comparativos...")
        try:
            import subprocess
            graph_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../graphs/generate_graphs.py")
            subprocess.run(["python3", graph_script])
        except Exception as e:
            print(f"Erro ao gerar gráficos automaticamente: {e}")

