from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import tempfile
import time
from rearm.app import build_app


def main():
    parser=argparse.ArgumentParser(description="Baseline → injury → heal → restore → repeat injury → recognize")
    parser.add_argument("--sim",action="store_true",required=True)
    parser.add_argument("--data-dir")
    args=parser.parse_args()
    Path("runtime").mkdir(exist_ok=True)
    data_dir=args.data_dir or tempfile.mkdtemp(prefix="demo-",dir="runtime")
    app=build_app(data_dir=data_dir)
    start=time.perf_counter()
    def timeline(event):
        if event.kind in ("state","alarm","diagnosis","switch","version_committed","rejected"):
            detail=event.data.get("state",event.data.get("version_id",""))
            if event.kind=="diagnosis": detail=event.data["diagnosis"]["best"]["name"]
            print(f"{time.perf_counter()-start:7.3f}s  {event.kind:18} {detail}",flush=True)
    app.bus.subscribe(timeline)
    app.baseline()
    for kind in ("j1","restore","j1"):
        app.command("inject",{"kind":kind,"amount":1 if kind=="j1" else 0})
        app.command("selfcheck",{})
        print(f"Recovery shots: {app.last_recovery_shots}; HEAD {app.store.head().id}")
    print(f"Logs: {data_dir}")


if __name__ == "__main__": main()
