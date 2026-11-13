from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
import json
from rearm.app import build_app
from rearm.types import jsonable


def main():
    parser=argparse.ArgumentParser(description="Train on clean chronological log data and gate on temporal holdout")
    parser.add_argument("--data-dir",default="runtime")
    args=parser.parse_args()
    app=build_app(data_dir=args.data_dir)
    try: print(json.dumps(jsonable(app.retrain()),ensure_ascii=False,indent=2))
    except ValueError as error: parser.exit(1,str(error)+"\n")


if __name__ == "__main__": main()
