import sys
import os
import argparse

# Add the current directory to sys.path to allow relative imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from simulator import run_simulation

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DASH Adaptive Streaming Client")
    parser.add_argument("-n", "--segments", type=int, default=20, help="Number of segments to download")
    parser.add_argument("-p", "--policy", type=str, choices=["baseline", "buffer", "heuristic", "all", "all_simultaneous"], default="baseline", help="ABR Policy to use")
    parser.add_argument("-g", "--generate", action="store_true", help="Automatically generate graphs after finishing")
    parser.add_argument("--gui", action="store_true", help="Launch the Desktop GUI")
    
    args = parser.parse_args()
    
    if args.gui:
        try:
            from gui import DASHFrontend
            app = DASHFrontend()
            app.mainloop()
            sys.exit(0)
        except ImportError as e:
            print(f"Error loading GUI: {e}")
            sys.exit(1)

    if args.policy in ["all", "all_simultaneous"]:
        print(f"\nExecuting simultaneous batch run for all policies (same network trace)")
        run_simulation(args.segments, "all_simultaneous")
    else:
        run_simulation(args.segments, args.policy)

    if args.generate:
        print("\nGenerating comparison graphs...")
        try:
            import subprocess
            graph_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../graphs/generate_graphs.py")
            subprocess.run(["python3", graph_script])
        except Exception as e:
            print(f"Could not auto-generate graphs: {e}")
