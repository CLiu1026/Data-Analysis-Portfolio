#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
CV_PYTHON='/Users/liuchi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
if [[ ! -x "$CV_PYTHON" ]]; then
  CV_PYTHON=python3
fi
"$CV_PYTHON" run_analysis.py
open 'outputs/dashboard.html'
printf '\n分析已完成，按回车关闭。\n'
read
