from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
from dataclasses import replace
import numpy as np
from rearm.app import build_app
from rearm.config import load_config


def main():
    parser=argparse.ArgumentParser(description="Collect genuine simulator measurements into JSONL")
    parser.add_argument("--sim",action="store_true",required=True)
    parser.add_argument("--shots",type=int,default=300)
    parser.add_argument("--data-dir",default="runtime")
    parser.add_argument("--nongeometric",action="store_true")
    parser.add_argument("--weight",action="store_true")
    args=parser.parse_args()
    if args.shots < 1: parser.error("--shots must be positive")
    config=load_config(Path(__file__).resolve().parents[1]/"config")
    if args.nongeometric: config=replace(config,sim=config.sim | {"nongeometric":True})
    app=build_app(config,args.data_dir)
    if args.weight: app.command("inject",{"kind":"weight"})
    rng=np.random.default_rng(config.sim["seed"])
    for _ in range(args.shots): app.step(app.probe_pool[int(rng.integers(len(app.probe_pool)))])
    print(f"Collected {args.shots} task shots; total {app.sequence}, alarms {app.alarms}; {args.data_dir}/shots.jsonl")


if __name__ == "__main__": main()
