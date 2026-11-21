#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi
[ -f data/demo/manifest.json ] || .venv/bin/python tools/make_demo.py
.venv/bin/python app.py
