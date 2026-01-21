#!/bin/bash

# Path to the virtual environment
VENV_PATH="/home/pi/Projects/Wallbox/env"
PROJECT_DIR="/home/pi/Projects/Wallbox"
LOG_DIR="$PROJECT_DIR/logs"

# Create logs folder if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to run a Python script with auto-restart and logging
run_script() {
    local script_name=$1
    local log_file="$LOG_DIR/${script_name%.py}.log"

    echo "Starting $script_name..." >> "$log_file"

    while true; do
        # Activate virtualenv and run script
        source "$VENV_PATH/bin/activate"
        python "$PROJECT_DIR/$script_name" >> "$log_file" 2>&1

        # Log crash and restart
        echo "$(date '+%Y-%m-%d %H:%M:%S') - $script_name crashed, restarting in 5 seconds..." >> "$log_file"
        sleep 5
    done
}

# Start all scripts in background
run_script "energy_main.py" &
run_script "energy_display.py" &
run_script "server.py" &
run_script "main.py" &

# Optional: log that all scripts were started
echo "$(date '+%Y-%m-%d %H:%M:%S') - All scripts started" >> "$LOG_DIR/startup.log"

# Keep script alive for systemd
wait
