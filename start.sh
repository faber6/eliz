#!/bin/sh
export DISCORD_TOKEN=""
export CONFIG="aya" # character (.json) in config
# export ENDPOINT="192.168.2.59" # global endpoint

venv/bin/python main.py
echo "Exited"