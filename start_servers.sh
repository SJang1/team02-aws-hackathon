#!/bin/bash

echo "Starting backend server (imsi.py) on port 5000..."
echo "Press Ctrl+C to stop"
python3 imsi_new.py &
python3 front/app.py &
