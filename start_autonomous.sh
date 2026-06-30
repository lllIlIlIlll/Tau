#!/bin/bash
set -e

cd "$(dirname "$0")"

nohup python3 -u -m core.taumain --reflect reflect/autonomous.py > autonomous.log 2>&1 & echo $! > autonomous.pid

echo "started autonomous, pid=$(cat autonomous.pid)"
echo "log: $(pwd)/autonomous.log"