#!/bin/sh
# export DISCORD_TOKEN=""
# export DISCORD_PREFIX="?"
# export DISCORD_STATUS="off"
# export CONFIG="aya"
# export ENDPOINT="192.168.2.59"

$(dirname "$0")/venv/bin/python $(dirname "$0")/main.py
echo "Exited"
