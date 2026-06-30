#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ -f autonomous.pid ]; then
  kill "$(cat autonomous.pid)" && rm -f autonomous.pid
  echo "autonomous stopped"
else
  echo "autonomous.pid not found"
fi