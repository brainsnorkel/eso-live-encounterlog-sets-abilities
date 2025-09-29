#!/bin/bash
# ESO Live Encounter Log Sets & Abilities Analyzer - Linux Launcher
# Version 0.2.3

echo "ESO Live Encounter Log Sets & Abilities Analyzer v0.2.3"
echo "========================================================"
echo ""

# Check if esolog-tail executable exists
if [ ! -f "./esolog-tail" ]; then
    echo "Error: esolog-tail executable not found!"
    echo "Please ensure you're running this script from the installer directory."
    exit 1
fi

# Make executable if needed
chmod +x ./esolog-tail

# Run the analyzer with all passed arguments
echo "Starting ESO Log Analyzer..."
echo "Usage: ./esolog-tail --help for options"
echo ""

./esolog-tail "$@"
