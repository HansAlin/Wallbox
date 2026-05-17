#!/usr/bin/bash

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
    local max_lines=10000

    echo "Starting $script_name..." >> "$log_file"

    while true; do

        # Background log trimmer
        (
            while true; do
                line_count=$(wc -l < "$log_file" 2>/dev/null || echo 0)

                if [ "$line_count" -gt "$max_lines" ]; then
                    tail -n "$max_lines" "$log_file" > "${log_file}.tmp"
                    cat "${log_file}.tmp" > "$log_file"
                    rm "${log_file}.tmp"
                fi

                sleep 10
            done
        ) &

        trim_pid=$!

        # Activate virtualenv and run script
        source "$VENV_PATH/bin/activate"
        python -u "$PROJECT_DIR/$script_name" >> "$log_file" 2>&1

        # Stop trimmer if python exits
        kill $trim_pid 2>/dev/null

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
