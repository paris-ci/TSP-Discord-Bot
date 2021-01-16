#!/usr/bin/env bash
cd /home/django/tsp_bot
/usr/bin/screen -dmS tsp bash -c 'while true; do python3.6 main.py; clear; sleep 1.5; done'
