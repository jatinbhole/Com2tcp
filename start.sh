#!/bin/bash

# Serial to TCP Forwarder Startup Script

echo "================================================"
echo "  Serial Port to TCP Forwarder"
echo "================================================"
echo ""
echo "Starting web service on http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the Flask web service
python3 web_service.py
