#!/bin/sh
# usage: serve.sh <repo> <port> <datadir>   (sim + nongeometric, 127.0.0.1 only)
cd "$1" && exec .venv/bin/python -c "
import sys,uvicorn
orig=uvicorn.run
uvicorn.run=lambda app,**k: orig(app,host='127.0.0.1',port=$2,log_level='warning')
sys.argv=['x','--sim','--nongeometric','--data-dir','$3']
from rearm.app import serve_ui
serve_ui()"
