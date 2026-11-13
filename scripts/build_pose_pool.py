from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import numpy as np
from rearm.app import build_app


def main():
    parser=argparse.ArgumentParser(description="Build validated nominal and robust self-check pose pools")
    parser.add_argument("--output",default="runtime/pose_pool.npz")
    args=parser.parse_args()
    app=build_app()
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,poses=app.pool,probes=app.probe_pool)
    print(f"Saved {len(app.pool)} candidate poses and {len(app.probe_pool)} robust poses to {path}")


if __name__ == "__main__": main()
