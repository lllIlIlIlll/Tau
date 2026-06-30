#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -f scheduler.pid ]; then
  kill "$(cat scheduler.pid)" && rm -f scheduler.pid
  echo "scheduler stopped"
else
  echo "scheduler.pid not found"
fi