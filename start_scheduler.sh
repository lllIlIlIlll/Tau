#!/bin/bash
set -e

cd "$(dirname "$0")"

nohup python3 -u -m core.taumain --reflect reflect/scheduler.py > scheduler.log 2>&1 & echo $! > scheduler.pid

echo "started scheduler, pid=$(cat scheduler.pid)"
echo "log: $(pwd)/scheduler.log"